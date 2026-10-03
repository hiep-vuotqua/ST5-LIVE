"""
ST5 CORE-SCAN — 2 luật song song (DCM + GVR)
DCM: VolR>1.5, ROC10>4, MACD>0, ADX>19, MA200+MA50, hold>=3
GVR: VolR>1.2, ROC10>4, MACD>0, ADX>27, no-MA, hold>=3
"""
import os, sys, json, time
from datetime import datetime
import pytz, requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_core_scan import (
    DCM_BASKET, GVR_BASKET, RULE_PARAMS,
    TIMEZONE, STATE_FILE, TELEGRAM_TITLE, DELAY_BETWEEN_TICKERS,
)
from data_core_scan import get_intraday_data
from indicators import add_v14_indicators

VN_TZ = pytz.timezone(TIMEZONE)
now = datetime.now(VN_TZ)
print(f"===== {TELEGRAM_TITLE} — {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")

if now.weekday() >= 5:
    print("Cuối tuần — bỏ qua")
    sys.exit(0)

state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), STATE_FILE)
state = {}
if os.path.exists(state_path):
    try:
        with open(state_path) as f:
            state = json.load(f)
    except Exception:
        state = {}

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat  = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[TG SKIP] {msg}")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": msg}, timeout=10)
    except Exception as e:
        print(f"[TG FAIL] {e}")

def check_signal(df, p):
    d = df.copy()
    d["MA50"]  = d["Close"].rolling(50).mean()
    d["MA200"] = d["Close"].rolling(200).mean()
    d = add_v14_indicators(d).dropna().reset_index(drop=True)
    if len(d) == 0:
        return None, None
    r = d.iloc[-1]
    conds = [
        r["VolumeRatio"] > p["volr"],
        r["ROC10"]       > p["roc"],
        r["MACD_Hist"]   > p["macd"],
        r["ADX14"]       > p["adx"],
    ]
    if p["ma200"]: conds.append(r["Close"] > r["MA200"])
    if p["ma50"]:  conds.append(r["Close"] > r["MA50"])
    return bool(all(conds)), r

buy_dcm, sell_dcm, buy_gvr, sell_gvr = [], [], [], []

print(f"--- Luật DCM ({len(DCM_BASKET)} mã) ---")
for ticker in DCM_BASKET:
    key = f"{ticker}_DCM"
    try:
        df = get_intraday_data(ticker, days=400)
        if len(df) == 0:
            time.sleep(DELAY_BETWEEN_TICKERS); continue
        sig, r = check_signal(df, RULE_PARAMS["DCM"])
        if sig is None:
            time.sleep(DELAY_BETWEEN_TICKERS); continue
        prev = state.get(key, {}).get("signal", False)
        print(f"  [{ticker}] close={r['Close']:.2f} ADX={r['ADX14']:.2f} sig={sig} prev={prev}")
        if sig and not prev:
            buy_dcm.append(ticker)
        elif (not sig) and prev:
            sell_dcm.append(ticker)
        state[key] = {"signal": sig, "date": str(now.date())}
        time.sleep(DELAY_BETWEEN_TICKERS)
    except Exception as e:
        print(f"  [{ticker}] ERR: {str(e)[:120]}")
        time.sleep(DELAY_BETWEEN_TICKERS)

print(f"--- Luật GVR ({len(GVR_BASKET)} mã) ---")
for ticker in GVR_BASKET:
    key = f"{ticker}_GVR"
    try:
        df = get_intraday_data(ticker, days=400)
        if len(df) == 0:
            time.sleep(DELAY_BETWEEN_TICKERS); continue
        sig, r = check_signal(df, RULE_PARAMS["GVR"])
        if sig is None:
            time.sleep(DELAY_BETWEEN_TICKERS); continue
        prev = state.get(key, {}).get("signal", False)
        print(f"  [{ticker}] close={r['Close']:.2f} ADX={r['ADX14']:.2f} sig={sig} prev={prev}")
        if sig and not prev:
            buy_gvr.append(ticker)
        elif (not sig) and prev:
            sell_gvr.append(ticker)
        state[key] = {"signal": sig, "date": str(now.date())}
        time.sleep(DELAY_BETWEEN_TICKERS)
    except Exception as e:
        print(f"  [{ticker}] ERR: {str(e)[:120]}")
        time.sleep(DELAY_BETWEEN_TICKERS)

with open(state_path, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

lines = [f"📊 {TELEGRAM_TITLE} — {now.strftime('%Y-%m-%d %H:%M')}"]
if buy_dcm:  lines.append(f"🟢 DCM BUY:  {', '.join(buy_dcm)}")
if sell_dcm: lines.append(f"🔴 DCM SELL: {', '.join(sell_dcm)}")
if buy_gvr:  lines.append(f"🟢 GVR BUY:  {', '.join(buy_gvr)}")
if sell_gvr: lines.append(f"🔴 GVR SELL: {', '.join(sell_gvr)}")

if len(lines) > 1:
    send_telegram("\n".join(lines))
else:
    print("Không có tín hiệu mới")

print(f"\n===== DONE — DCM BUY:{len(buy_dcm)} SELL:{len(sell_dcm)} | GVR BUY:{len(buy_gvr)} SELL:{len(sell_gvr)} =====")
