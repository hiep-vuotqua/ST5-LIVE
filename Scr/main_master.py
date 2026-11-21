# ST5 MASTER v3 - VNDirect API (Chuan TradingView + Stop Loss + Hard Hold Cap)
import sys
import os, json, time
from datetime import datetime, timedelta
import pytz, requests
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_master_v3 import (
    RULES, POSITION_SIZE, MAX_POSITIONS, CAPITAL_INITIAL,
    STOP_LOSS_PCT, HARD_MAX_HOLD_DAYS,
    TIMEZONE, STATE_FILE, LOG_FILE, TELEGRAM_TITLE, DELAY_BETWEEN_TICKERS,
)

def get_intraday_data(ticker, days=450):
    end = datetime.now()
    start = end - timedelta(days=days)
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())

    url = f"https://dchart-api.vndirect.com.vn/dchart/history?resolution=D&symbol={ticker}&from={start_ts}&to={end_ts}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("s") == "ok" and "t" in data:
                df = pd.DataFrame({
                    "Date": pd.to_datetime(data["t"], unit="s") + pd.Timedelta(hours=7),
                    "Open": data["o"],
                    "High": data["h"],
                    "Low": data["l"],
                    "Close": data["c"],
                    "Volume": data["v"]
                })
                df["Date"] = df["Date"].dt.normalize()
                return df.dropna().drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    except Exception:
        pass

    print(f" [{ticker}] FAIL to pull data.")
    return pd.DataFrame()

def _calc_indicators_fallback(df):
    d = df.copy()
    d['MA50'] = d['Close'].rolling(50).mean()
    d['MA200'] = d['Close'].rolling(200).mean()
    d['Vol_MA20'] = d['Volume'].rolling(20).mean()
    d['VolumeRatio'] = d['Volume'] / d['Vol_MA20']
    d['ROC10'] = (d['Close'] / d['Close'].shift(10) - 1) * 100

    exp12 = d['Close'].ewm(span=12, adjust=False).mean()
    exp26 = d['Close'].ewm(span=26, adjust=False).mean()
    d['MACD'] = exp12 - exp26
    d['MACD_Signal'] = d['MACD'].ewm(span=9, adjust=False).mean()
    d['MACD_Hist'] = d['MACD'] - d['MACD_Signal']

    high, low, close = d['High'], d['Low'], d['Close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    def wilder_smooth(series):
        return series.ewm(alpha=1/14, adjust=False).mean()

    d['ATR14'] = wilder_smooth(tr)
    d['Plus_DI'] = 100 * (pd.Series(plus_dm, index=d.index).pipe(wilder_smooth) / d['ATR14'])
    d['Minus_DI'] = 100 * (pd.Series(minus_dm, index=d.index).pipe(wilder_smooth) / d['ATR14'])
    dx = 100 * abs(d['Plus_DI'] - d['Minus_DI']) / (d['Plus_DI'] + d['Minus_DI']).replace(0, np.nan)
    d['ADX14'] = dx.pipe(wilder_smooth)

    return d

VN_TZ = pytz.timezone(TIMEZONE)
now = datetime.now(VN_TZ)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
state_path = os.path.join(BASE_DIR, STATE_FILE)
os.makedirs(os.path.dirname(state_path), exist_ok=True)

print(f"===== {TELEGRAM_TITLE} - {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")

is_manual = (
    os.environ.get("IS_MANUAL", "false").lower() == "true"
    or os.environ.get("GITHUB_EVENT_NAME", "").lower() == "workflow_dispatch"
)
if is_manual:
    print("[CHE DO THU CONG] Bo qua kiem tra gio giao dich.")

if now.weekday() >= 5 and not is_manual:
    print("Cuoi tuan - bo qua")
    sys.exit(0)

current_time = now.hour * 100 + now.minute
if (current_time < 900 or current_time > 1500) and not is_manual:
    print(f"[{now.strftime('%H:%M')}] Ngoai gio giao dich (09:00 - 15:00). Bo qua.")
    sys.exit(0)

state = {"positions": {}, "last_signals": {}, "cash": CAPITAL_INITIAL, "last_run": None}
if os.path.exists(state_path):
    try:
        with open(state_path) as f:
            loaded = json.load(f)
            for k in state:
                if k in loaded:
                    state[k] = loaded[k]
    except Exception as e:
        print(f"[state load fail] {e}")

ticker_cache = {}
success_tickers = set()
fail_tickers = set()

def get_cached_data(tk, days=450):
    if tk in ticker_cache:
        return ticker_cache[tk]
    df = get_intraday_data(tk, days=days)
    ticker_cache[tk] = df
    return df

def check_signal(df, p):
    d = _calc_indicators_fallback(df).dropna().reset_index(drop=True)
    if len(d) == 0:
        return None, None
    r = d.iloc[-1]
    conds = [
        r["VolumeRatio"] > p["volr"],
        r["ROC10"] > p["roc"],
        r["MACD_Hist"] > p["macd"],
        r["ADX14"] > p["adx"],
    ]
    if p.get("ma200"):
        conds.append(r["Close"] > r["MA200"])
    if p.get("ma50"):
        conds.append(r["Close"] > r["MA50"])
    return bool(all(conds)), r

def business_days_since(date_str, now_dt):
    d1 = datetime.strptime(date_str, "%Y-%m-%d")
    n = 0
    cur = d1
    while cur.date() < now_dt.date():
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[TG SKIP]\n{msg}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[TG FAIL] {e}")

signal_map = {}

for rule_name, rule in RULES.items():
    print(f"\n--- {rule_name} ({len(rule['tickers'])} ma) ---")
    for tk in rule["tickers"]:
        key = f"{tk}__{rule_name}"
        try:
            df = get_cached_data(tk)
            if len(df) < 50:
                fail_tickers.add(tk)
                print(f"  [{tk}] Bo qua (chi co {len(df)} nen)")
                continue

            success_tickers.add(tk)
            sig, r = check_signal(df, rule)
            if sig is None:
                print(f"  [{tk}] Loi tinh toan")
                continue

            print(f"  [{tk}] {'MUA' if sig else 'Khong'} | {len(df)} nen | VolR={r['VolumeRatio']:.2f} ADX={r['ADX14']:.1f} ROC={r['ROC10']:.1f}")

            prev = state["last_signals"].get(key, False)
            pos = state["positions"].get(key)

            if pos:
                hold = business_days_since(pos["entry_date"], now)
                unrl_pct = (float(r["Close"]) / float(pos["entry_price"]) - 1.0) * 100.0
                hit_stop = unrl_pct <= -abs(STOP_LOSS_PCT)
                hit_hard_cap = hold >= HARD_MAX_HOLD_DAYS
                hit_rule_exit = (not sig) and prev and (hold >= rule["mh"])

                exit_tag = None
                if hit_stop:
                    exit_tag = "SL"
                elif hit_hard_cap:
                    exit_tag = "CAP20"
                elif hit_rule_exit:
                    exit_tag = "MH"

                if exit_tag:
                    ret = float(r["Close"]) / float(pos["entry_price"])
                    state["cash"] += pos["size"] * ret
                    signal_map.setdefault(tk, []).append({
                        "rule": rule_name,
                        "action": "SELL",
                        "tag": exit_tag,
                        "ret": ret - 1.0,
                        "hold": hold,
                    })
                    del state["positions"][key]

            elif sig and not prev:
                already_held = any(k.startswith(f"{tk}__") for k in state["positions"])
                if not already_held and len(state["positions"]) < MAX_POSITIONS and state["cash"] >= POSITION_SIZE:
                    state["cash"] -= POSITION_SIZE
                    state["positions"][key] = {
                        "entry_date": str(now.date()),
                        "entry_price": float(r["Close"]),
                        "size": POSITION_SIZE,
                        "volr": round(float(r["VolumeRatio"]), 2),
                        "adx": round(float(r["ADX14"]), 2),
                    }
                    signal_map.setdefault(tk, []).append({
                        "rule": rule_name,
                        "action": "BUY",
                        "volr": r["VolumeRatio"],
                        "adx": r["ADX14"],
                        "roc": r["ROC10"],
                    })

            state["last_signals"][key] = sig
            time.sleep(DELAY_BETWEEN_TICKERS)
        except Exception:
            fail_tickers.add(tk)
            time.sleep(DELAY_BETWEEN_TICKERS)

print(f"\n===== TOM TAT: Lay duoc {len(success_tickers)} ma, Bo qua {len(fail_tickers)} ma =====")
state["last_run"] = str(now)

buys = {tk: sigs for tk, sigs in signal_map.items() if any(s["action"] == "BUY" for s in sigs)}
sells = {tk: sigs for tk, sigs in signal_map.items() if any(s["action"] == "SELL" for s in sigs)}

with open(state_path, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

if buys or sells:
    lines = [f"<b>{TELEGRAM_TITLE}</b> - {now.strftime('%Y-%m-%d %H:%M')}"]
    if buys:
        lines.append(f"\n<b>MUA ({len(buys)}):</b>")
        for tk, sigs in sorted(buys.items(), key=lambda x: -len([s for s in x[1] if s["action"] == "BUY"])):
            buy_sigs = [s for s in sigs if s["action"] == "BUY"]
            strength = "[FIRE]" * min(len(buy_sigs), 3)
            rules_str = " + ".join(s["rule"] for s in buy_sigs)
            volr = buy_sigs[0]["volr"]
            adx = buy_sigs[0]["adx"]
            roc = buy_sigs[0]["roc"]
            lines.append(f"  {strength} <b>{tk}</b> - {rules_str}")
            lines.append(f"     VolR={volr:.2f} ADX={adx:.1f} ROC={roc:.1f}")
    if sells:
        lines.append(f"\n<b>BAN ({len(sells)}):</b>")
        for tk, sigs in sells.items():
            for s in [x for x in sigs if x["action"] == "SELL"]:
                lines.append(f"  - {tk} - {s['rule']} [{s['tag']}] (hold {s['hold']}d, {s['ret']*100:+.2f}%)")
    lines.append(f"\nCash: {state['cash']/1e9:.4f} ty | Pos: {len(state['positions'])}")
    send_telegram("\n".join(lines))
else:
    msg = (
        f"<b>{TELEGRAM_TITLE}</b> - {now.strftime('%H:%M')}\n"
        f"Trang thai: Khong co tin hieu moi.\n"
        f"Cash: {state['cash']/1e9:.4f} ty | Dang giu: {len(state['positions'])} ma"
    )
    send_telegram(msg)
    print("\nKhong co tin hieu moi - Da gui tin nhan Heartbeat.")

print(f"\n===== DONE - {len(buys)} BUY signals, {len(sells)} SELL signals =====")
