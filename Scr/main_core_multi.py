# main_core_multi.py — scan đa config
import json, os, time, requests
import pandas as pd, numpy as np
from datetime import datetime
from config_core_multi import (
    POOL_CONFIG, FEE_PER_ROUND, TIMEZONE,
    STATE_FILE, TELEGRAM_TITLE, DELAY_BETWEEN_TICKERS
)
from data_core_multi import get_data

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[WARN] Missing Telegram secrets"); return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        print(f"[TG] {r.status_code}")
    except Exception as e:
        print(f"[ERR] Telegram: {e}")

def adx_wilder(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    up = h.diff(); dn = -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    pdm = pd.Series(pdm, index=df.index).ewm(alpha=1/n, adjust=False).mean()
    mdm = pd.Series(mdm, index=df.index).ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pdm/atr; mdi = 100*mdm/atr
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()

def compute_indicators(df):
    df = df.copy()
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["volR"]     = df["volume"] / df["vol_ma20"]
    df["roc10"]    = (df["close"]-df["close"].shift(10))/df["close"].shift(10)*100
    e12 = df["close"].ewm(span=12, adjust=False).mean()
    e26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    df["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
    df["ma50"]  = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()
    df["adx14"] = adx_wilder(df, 14)
    return df

def check_signal(df, cfg):
    last = df.iloc[-1]
    buy = (
        last["volR"] >= cfg["volR"] and
        last["roc10"] >= cfg["roc"] and
        last["macd_hist"] > cfg["macd"] and
        last["adx14"] >= cfg["adx"] and
        ((not cfg["ma200"]) or last["close"] > last["ma200"]) and
        ((not cfg["ma50"])  or last["close"] > last["ma50"])
    )
    return {
        "buy": bool(buy),
        "close": float(last["close"]),
        "adx": float(last["adx14"]),
        "volR": float(last["volR"]),
        "roc10": float(last["roc10"]),
        "macd_h": float(last["macd_hist"]),
        "date": last.name.strftime("%Y-%m-%d"),
    }

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE) as f: return json.load(f)
    except: return {}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def main():
    state = load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[{TELEGRAM_TITLE}] {today} — {len(POOL_CONFIG)} mã")

    alerts = []
    for tk, cfg in POOL_CONFIG.items():
        try:
            df = get_data(tk, days=500)
            if df is None or len(df) < 250:
                print(f"  {tk}: SKIP ({len(df) if df is not None else 0} nến)")
                time.sleep(DELAY_BETWEEN_TICKERS); continue

            df = compute_indicators(df)
            sig = check_signal(df, cfg)
            mh = cfg["mh"]

            t_state = state.get(tk, {})
            t_state.setdefault("in_position", False)
            t_state.setdefault("buy_date", None)
            t_state.setdefault("buy_price", None)
            t_state.setdefault("alerted_buy_dates", [])

            if sig["buy"] and not t_state["in_position"]:
                if sig["date"] not in t_state["alerted_buy_dates"]:
                    alerts.append(
                        f"🟢 MUA <b>{tk}</b> @ {sig['close']:.2f}\n"
                        f"   nến {sig['date']} | ADX={sig['adx']:.1f} VolR={sig['volR']:.2f} ROC={sig['roc10']:.1f} | MH={mh}"
                    )
                    t_state["in_position"] = True
                    t_state["buy_date"] = sig["date"]
                    t_state["buy_price"] = sig["close"]
                    t_state["alerted_buy_dates"].append(sig["date"])

            if t_state["in_position"] and t_state["buy_date"]:
                bd = pd.to_datetime(t_state["buy_date"])
                bars_after = int((df.index > bd).sum())
                if bars_after >= mh + 1:
                    alerts.append(
                        f"🔴 BÁN <b>{tk}</b> @ {sig['close']:.2f} (giữ {bars_after} nến, MH={mh})"
                    )
                    t_state["in_position"] = False
                    t_state["buy_date"] = None
                    t_state["buy_price"] = None

            state[tk] = t_state
            print(f"  {tk}: close={sig['close']:.2f} ADX={sig['adx']:.1f} volR={sig['volR']:.2f} "
                  f"buy={sig['buy']} in_pos={t_state['in_position']}")
            time.sleep(DELAY_BETWEEN_TICKERS)
        except Exception as e:
            print(f"  {tk}: ERR {str(e)[:100]}")

    save_state(state)

    if alerts:
        msg = f"<b>{TELEGRAM_TITLE}</b> — {today}\n\n" + "\n\n".join(alerts)
        send_telegram(msg)
        print(f"[DONE] Sent {len(alerts)} alerts")
    else:
        print("[DONE] No alerts")

if __name__ == "__main__":
    main() 
