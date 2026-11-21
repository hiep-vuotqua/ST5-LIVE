# ST5 B1FULL - VNDirect API (Trail 10% + Time Gatekeeper)
import os, sys, json, time, requests, pytz
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_b1full import B1FULL_RULES, CAPITAL_ALLOC, TRAIL_PCT, TELEGRAM_PREFIX

# ---------- DATA PULLING (VNDIRECT) ----------
def pull_daily(ticker, days=400):
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
    return pd.DataFrame()

# ---------- INDICATORS ----------
def wilder_average(series, period):
    x = series.astype(float).values
    out = np.full(len(x), np.nan)
    valid = np.where(np.isfinite(x))[0]
    if len(valid) < period: return pd.Series(out, index=series.index)
    first = valid[0]; seed_end = first + period
    if seed_end > len(x): return pd.Series(out, index=series.index)
    out[seed_end-1] = np.mean(x[first:seed_end])
    for i in range(seed_end, len(x)):
        if np.isfinite(x[i]) and np.isfinite(out[i-1]):
            out[i] = (out[i-1] * (period-1) + x[i]) / period
    return pd.Series(out, index=series.index)

def prepare(df):
    d = df.copy()
    if "VolR" not in d.columns:
        d["VolR"] = d["Volume"] / d["Volume"].rolling(20).mean()
    if "ROC10" not in d.columns:
        d["ROC10"] = d["Close"].pct_change(10) * 100.0
    if "MACD_Hist" not in d.columns:
        e12 = d["Close"].ewm(span=12, adjust=False).mean()
        e26 = d["Close"].ewm(span=26, adjust=False).mean()
        m = e12 - e26
        d["MACD_Hist"] = m - m.ewm(span=9, adjust=False).mean()
    if "MA50" not in d.columns:
        d["MA50"] = d["Close"].rolling(50).mean()
    if "MA200" not in d.columns:
        d["MA200"] = d["Close"].rolling(200).mean()
    
    if "ADX14" not in d.columns:
        high, low, close = d["High"], d["Low"], d["Close"]
        tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
        up, down = high.diff(), -low.diff()
        plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0), index=d.index)
        minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0), index=d.index)
        
        atr = wilder_average(tr, 14)
        plus_sm = wilder_average(plus_dm, 14)
        minus_sm = wilder_average(minus_dm, 14)
        plus_di = 100 * plus_sm / atr
        minus_di = 100 * minus_sm / atr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        d["ADX14"] = wilder_average(dx, 14)
        
    return d

# ---------- SETUP ----------
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh") # Cố định timezone cho B1FULL
now = datetime.now(VN_TZ)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "live_state_b1full.json")

print(f"===== ST5 B1FULL - {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")
print("Nguon du lieu: VNDirect")

is_manual = (
    os.environ.get("IS_MANUAL", "false").lower() == "true"
    or os.environ.get("GITHUB_EVENT_NAME", "").lower() == "workflow_dispatch"
)
if is_manual:
    print("[CHE DO THU CONG] Bo qua kiem tra ngay cuoi tuan va gio giao dich.")

if now.weekday() >= 5 and not is_manual:
    print("Cuoi tuan - bo qua"); sys.exit(0)

current_time = now.hour * 100 + now.minute
if (current_time < 900 or current_time > 1500) and not is_manual:
    print(f"[{now.strftime('%H:%M')}] Ngoai gio giao dich. Bo qua."); sys.exit(0)

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE) as f: return json.load(f)
    except: return {}

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat  = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[TG SKIP]\n{msg}"); return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"[TG FAIL] {e}")

def check_signal(row, cfg):
    for col in ["ADX14", "VolR", "ROC10"]:
        if col not in row.index or pd.isna(row[col]): return False
    if row["ADX14"] < cfg["adx"]: return False
    if row["VolR"]  < cfg["volr"]: return False
    if row["ROC10"] < cfg["roc"]: return False
    if cfg.get("macd") is not None:
        if "MACD_Hist" not in row.index or pd.isna(row["MACD_Hist"]): return False
        if row["MACD_Hist"] <= cfg["macd"]: return False
    if cfg.get("ma50") and (pd.isna(row["MA50"]) or row["Close"] <= row["MA50"]): return False
    if cfg.get("ma200") and (pd.isna(row["MA200"]) or row["Close"] <= row["MA200"]): return False
    return True

# ---------- MAIN ----------
def main():
    today_str = now.strftime("%Y-%m-%d")
    state = load_state()
    nav = CAPITAL_ALLOC["nav"]
    size_vnd = nav * CAPITAL_ALLOC["size_pct"]
    max_pos = CAPITAL_ALLOC["max_positions"]

    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] B1FULL — state {len(state)}/{max_pos} | TRAIL={TRAIL_PCT}%")

    buys, sells, errors = [], [], []

    for ticker, cfg in B1FULL_RULES.items():
        print(f"  pull {ticker}...", end=" ", flush=True)
        df = pull_daily(ticker, days=400) # Lấy 400 ngày nến
        if df is None or len(df) < 210:
            print("no data / <210 rows")
            errors.append(ticker)
            continue
        df = prepare(df)
        last = df.iloc[-1]

        if ticker in state:
            pos = state[ticker]
            hold_days = (pd.Timestamp(today_str) - pd.Timestamp(pos["entry_date"])).days
            old_peak = pos.get("peak_price", pos["entry_px"])
            new_peak = max(old_peak, float(last["Close"]))
            pos["peak_price"] = new_peak

            trail_line = new_peak * (1 - TRAIL_PCT / 100)
            exit_reason = None
            if float(last["Close"]) <= trail_line: exit_reason = "TRAIL"
            elif hold_days >= cfg["mh"]: exit_reason = "HOLD"

            if exit_reason:
                exit_px = float(last["Close"])
                ret = (exit_px / pos["entry_px"] - 1) * 100
                pnl = size_vnd * ret / 100
                sells.append({"ticker": ticker, "hold": hold_days, "ret": ret, "pnl": pnl, "reason": exit_reason})
                del state[ticker]
                print(f"{exit_reason} (hold {hold_days}d, {ret:+.2f}%)")
                continue

            print(f"HOLD ({hold_days}/{cfg['mh']}d, peak={new_peak:.1f})")
            continue

        if len(state) >= max_pos:
            print(f"skip (full {max_pos})")
            continue
            
        if check_signal(last, cfg):
            entry_px = float(last["Close"])
            state[ticker] = {
                "entry_date": today_str, "entry_px": entry_px,
                "peak_price": entry_px, "variant": cfg.get("variant",""),
                "adx": float(last["ADX14"]), "volr": float(last["VolR"]), "roc": float(last["ROC10"]),
            }
            buys.append({"ticker": ticker, "variant": cfg.get("variant",""), "adx": float(last["ADX14"]), "volr": float(last["VolR"]), "roc": float(last["ROC10"]), "size_vnd": size_vnd})
            print(f"MUA (ADX={last['ADX14']:.1f} VolR={last['VolR']:.2f} ROC={last['ROC10']:.2f})")
        else:
            print("no signal")

    save_state(state)

    lines = [f"📊 <b>{TELEGRAM_PREFIX}</b> — {now.strftime('%Y-%m-%d %H:%M')}", f"<i>Trail {TRAIL_PCT:.0f}% | {len(B1FULL_RULES)} mã</i>"]
    if buys:
        lines.append(f"🟢 <b>MUA ({len(buys)})</b>:")
        for b in buys:
            lines.append(f"   • <b>{b['ticker']}</b> — {b['variant']} ({b['size_vnd']/1e6:.0f}tr) VolR={b['volr']:.2f} ADX={b['adx']:.1f} ROC={b['roc']:.2f}")
    if sells:
        lines.append(f"🔴 <b>BÁN ({len(sells)})</b>:")
        for s in sells:
            emoji = "🟢" if s['ret'] > 0 else "🔴"
            tag = "TRAIL" if s['reason'] == "TRAIL" else f"{s['hold']}d"
            lines.append(f"   {emoji} <b>{s['ticker']}</b> — {tag} {s['ret']:+.2f}% ({s['pnl']/1e6:+.1f}tr)")
    if not buys and not sells: lines.append("⏸ Không có signal")
    if errors: lines.append(f"⚠️ Lỗi pull: {', '.join(errors)}")
    cash_used = len(state) * size_vnd
    lines.append(f"💰 Pos: {len(state)}/{max_pos} | Deployed: {cash_used/1e9:.2f} tỷ | Cash: {(nav-cash_used)/1e9:.2f} tỷ")
    send_telegram("\n".join(lines))
    print(f"\n===== DONE =====")

if __name__ == "__main__":
    main()
