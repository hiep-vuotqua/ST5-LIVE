"""
ST5 CORE-SCAN — Tier sizing + portfolio tracking + log + alert
DCM: VolR>1.5, ROC10>4, MACD>0, ADX>19, MA200+MA50
GVR: VolR>1.2, ROC10>4, MACD>0, ADX>27, no-MA
Tier A(VolR>2.5)=150tr | B(1.5-2.5)=100tr | C(<1.5)=60tr
"""
import os, sys, json, time, csv
from datetime import datetime, timedelta
import pytz, requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_core_scan import (
    DCM_BASKET, GVR_BASKET, RULE_PARAMS,
    TIER_A_VOLR, TIER_B_VOLR, SIZE_A, SIZE_B, SIZE_C,
    CAPITAL_INITIAL, MAX_POSITIONS, DD_ALERT_THRESHOLD,
    TIMEZONE, STATE_FILE, LOG_FILE,
    TELEGRAM_TITLE, DELAY_BETWEEN_TICKERS,
)
from data_core_scan import get_intraday_data
from indicators import add_v14_indicators

VN_TZ = pytz.timezone(TIMEZONE)
now = datetime.now(VN_TZ)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
state_path = os.path.join(BASE_DIR, STATE_FILE)
log_path = os.path.join(BASE_DIR, LOG_FILE)

print(f"===== {TELEGRAM_TITLE} — {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")

if now.weekday() >= 5:
    print("Cuối tuần — bỏ qua")
    sys.exit(0)

# ============ LOAD STATE ============
state = {
    "positions": {},       # key = "TICKER_RULE" -> {entry_date, entry_price, size, tier, volr}
    "cash": CAPITAL_INITIAL,
    "peak_equity": CAPITAL_INITIAL,
    "last_signals": {},    # key = "TICKER_RULE" -> True/False
    "last_run": None,
}
if os.path.exists(state_path):
    try:
        with open(state_path) as f:
            loaded = json.load(f)
            for k, v in loaded.items():
                state[k] = v
    except Exception as e:
        print(f"[state load fail] {e}")

print(f"State: cash={state['cash']:,.0f} | positions={len(state['positions'])} | peak={state['peak_equity']:,.0f}")

# ============ HELPERS ============
def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat  = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"[TG SKIP]\n{msg}")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": msg, "parse_mode": "HTML"},
                      timeout=10)
    except Exception as e:
        print(f"[TG FAIL] {e}")

def check_signal(df, p):
    d = df.copy()
    d["MA50"]  = d["Close"].rolling(50).mean()
    d["MA200"] = d["Close"].rolling(200).mean()
    d = add_v14_indicators(d).dropna().reset_index(drop=True)
    if len(d) == 0: return None, None
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

def size_from_tier(volr):
    if volr > TIER_A_VOLR:    return SIZE_A, "A"
    elif volr >= TIER_B_VOLR: return SIZE_B, "B"
    else:                     return SIZE_C, "C"

def business_days_between(d1_str, d2):
    d1 = datetime.strptime(d1_str, "%Y-%m-%d")
    n = 0
    cur = d1
    while cur.date() < d2.date():
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n

# ============ LOG PREP ============
log_rows = []
log_header = ["timestamp", "ticker", "rule", "action", "tier", "volr",
              "size", "price", "cash_after", "equity_after", "dd_pct"]

def append_log(timestamp, ticker, rule, action, tier, volr, size, price, cash_after, equity_after, dd_pct):
    log_rows.append({
        "timestamp": timestamp, "ticker": ticker, "rule": rule, "action": action,
        "tier": tier, "volr": round(volr, 2) if volr else None,
        "size": int(size) if size else 0, "price": round(price, 2) if price else None,
        "cash_after": int(cash_after), "equity_after": int(equity_after),
        "dd_pct": round(dd_pct, 2),
    })

# ============ MAIN LOOP ============
buy_dcm, sell_dcm, buy_gvr, sell_gvr = [], [], [], []
price_cache = {}     # ticker -> last close (for MTM)

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
        price_cache[ticker] = r["Close"]
        prev = state["last_signals"].get(key, False)
        pos = state["positions"].get(key)

        # Decode action
        if sig and not prev and not pos:
            size, tier = size_from_tier(r["VolumeRatio"])
            if len(state["positions"]) < MAX_POSITIONS and state["cash"] >= size:
                state["cash"] -= size
                state["positions"][key] = {
                    "entry_date": str(now.date()),
                    "entry_price": r["Close"],
                    "size": size, "tier": tier,
                    "volr": round(r["VolumeRatio"], 2),
                }
                buy_dcm.append((ticker, tier, size))
                print(f"  [{ticker}] BUY {tier} size={size/1e6:.0f}tr volR={r['VolumeRatio']:.2f} close={r['Close']:.2f}")
                append_log(str(now), ticker, "DCM", "BUY", tier, r["VolumeRatio"], size, r["Close"], state["cash"], 0, 0)
            else:
                print(f"  [{ticker}] BUY signal but full/cash — skipped")
        elif (not sig) and prev and pos:
            hold = business_days_between(pos["entry_date"], now)
            if hold >= RULE_PARAMS["DCM"]["hold"]:
                ret = r["Close"] / pos["entry_price"]
                proceeds = pos["size"] * ret
                state["cash"] += proceeds
                sell_dcm.append((ticker, ret - 1))
                print(f"  [{ticker}] SELL hold={hold} ret={(ret-1)*100:+.2f}%")
                append_log(str(now), ticker, "DCM", "SELL", pos["tier"], pos["volr"], pos["size"], r["Close"], state["cash"], 0, 0)
                del state["positions"][key]
            else:
                print(f"  [{ticker}] EXIT signal but hold={hold} < 3 — hold")
        else:
            print(f"  [{ticker}] close={r['Close']:.2f} ADX={r['ADX14']:.2f} volR={r['VolumeRatio']:.2f} sig={sig}")

        state["last_signals"][key] = sig
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
        price_cache[ticker] = r["Close"]
        prev = state["last_signals"].get(key, False)
        pos = state["positions"].get(key)

        if sig and not prev and not pos:
            size, tier = size_from_tier(r["VolumeRatio"])
            if len(state["positions"]) < MAX_POSITIONS and state["cash"] >= size:
                state["cash"] -= size
                state["positions"][key] = {
                    "entry_date": str(now.date()),
                    "entry_price": r["Close"],
                    "size": size, "tier": tier,
                    "volr": round(r["VolumeRatio"], 2),
                }
                buy_gvr.append((ticker, tier, size))
                print(f"  [{ticker}] BUY {tier} size={size/1e6:.0f}tr volR={r['VolumeRatio']:.2f} close={r['Close']:.2f}")
                append_log(str(now), ticker, "GVR", "BUY", tier, r["VolumeRatio"], size, r["Close"], state["cash"], 0, 0)
            else:
                print(f"  [{ticker}] BUY signal but full/cash — skipped")
        elif (not sig) and prev and pos:
            hold = business_days_between(pos["entry_date"], now)
            if hold >= RULE_PARAMS["GVR"]["hold"]:
                ret = r["Close"] / pos["entry_price"]
                proceeds = pos["size"] * ret
                state["cash"] += proceeds
                sell_gvr.append((ticker, ret - 1))
                print(f"  [{ticker}] SELL hold={hold} ret={(ret-1)*100:+.2f}%")
                append_log(str(now), ticker, "GVR", "SELL", pos["tier"], pos["volr"], pos["size"], r["Close"], state["cash"], 0, 0)
                del state["positions"][key]
            else:
                print(f"  [{ticker}] EXIT signal but hold={hold} < 3 — hold")
        else:
            print(f"  [{ticker}] close={r['Close']:.2f} ADX={r['ADX14']:.2f} volR={r['VolumeRatio']:.2f} sig={sig}")

        state["last_signals"][key] = sig
        time.sleep(DELAY_BETWEEN_TICKERS)
    except Exception as e:
        print(f"  [{ticker}] ERR: {str(e)[:120]}")
        time.sleep(DELAY_BETWEEN_TICKERS)

# ============ EQUITY & DD ============
mtm = state["cash"]
for key, pos in state["positions"].items():
    tk = key.split("_")[0]
    if tk in price_cache:
        mtm += pos["size"] * (price_cache[tk] / pos["entry_price"])
    else:
        mtm += pos["size"]  # assume no change

peak = max(state["peak_equity"], mtm)
dd = (mtm - peak) / peak * 100 if peak > 0 else 0
state["peak_equity"] = peak
state["last_run"] = str(now)

print(f"\n===== EQUITY =====")
print(f"  Cash:      {state['cash']:>15,.0f} VNĐ")
print(f"  Positions: {len(state['positions'])}")
print(f"  MTM:       {mtm:>15,.0f} VNĐ")
print(f"  Peak:      {peak:>15,.0f} VNĐ")
print(f"  DD:        {dd:>14.2f}%")

# ============ SAVE STATE ============
with open(state_path, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

# ============ SAVE LOG ============
log_dir = os.path.dirname(log_path)
os.makedirs(log_dir, exist_ok=True)
file_exists = os.path.exists(log_path)
with open(log_path, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=log_header)
    if not file_exists:
        w.writeheader()
    for row in log_rows:
        w.writerow(row)

# ============ TELEGRAM ============
lines = [f"📊 <b>{TELEGRAM_TITLE}</b> — {now.strftime('%Y-%m-%d %H:%M')}"]

if buy_dcm or sell_dcm or buy_gvr or sell_gvr:
    if buy_dcm:
        lines.append("🟢 <b>DCM BUY:</b>")
        for tk, tier, sz in buy_dcm:
            lines.append(f"  • {tk} — Tier {tier} — {sz/1e6:.0f}tr")
    if sell_dcm:
        lines.append("🔴 <b>DCM SELL:</b>")
        for tk, ret in sell_dcm:
            lines.append(f"  • {tk} — {ret*100:+.2f}%")
    if buy_gvr:
        lines.append("🟢 <b>GVR BUY:</b>")
        for tk, tier, sz in buy_gvr:
            lines.append(f"  • {tk} — Tier {tier} — {sz/1e6:.0f}tr")
    if sell_gvr:
        lines.append("🔴 <b>GVR SELL:</b>")
        for tk, ret in sell_gvr:
            lines.append(f"  • {tk} — {ret*100:+.2f}%")
    lines.append(f"\n💰 MTM: {mtm/1e9:.4f} tỷ | Peak: {peak/1e9:.4f} tỷ | DD: {dd:+.2f}%")
    if dd < DD_ALERT_THRESHOLD:
        lines.append(f"⚠️ <b>CẢNH BÁO DD VƯỢT NGƯỠNG {DD_ALERT_THRESHOLD}%</b>")

send_telegram("\n".join(lines)) if (buy_dcm or sell_dcm or buy_gvr or sell_gvr) else None

print(f"\n===== DONE — DCM BUY:{len(buy_dcm)} SELL:{len(sell_dcm)} | GVR BUY:{len(buy_gvr)} SELL:{len(sell_gvr)} =====")
