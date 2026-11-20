"""
ST5 HIEP-SCAN - VNDirect API (Chuan TradingView, ho tro IS_MANUAL)
"""
import os, sys, json, time, csv
from datetime import datetime, timedelta
import pytz, requests
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_hiep_scan import (
    DCM_BASKET, GVR_BASKET, RULE_PARAMS,
    TIER_A_VOLR, TIER_B_VOLR, SIZE_A, SIZE_B, SIZE_C,
    CAPITAL_INITIAL, MAX_POSITIONS, DD_ALERT_THRESHOLD,
    TIMEZONE, STATE_FILE, LOG_FILE,
    TELEGRAM_TITLE, DELAY_BETWEEN_TICKERS,
)

# ---------- DATA PULLING (VNDIRECT) ----------
def get_intraday_data(ticker, days=400):
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
    except Exception as e:
        print(f" [{ticker}] Loi API VNDirect: {str(e)[:50]}")
    
    print(f" [{ticker}] FAIL to pull data.")
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

def add_indicators(df):
    d = df.copy()
    close, high, low, volume = d["Close"], d["High"], d["Low"], d["Volume"]
    d["MA50"] = close.rolling(50).mean()
    d["MA200"] = close.rolling(200).mean()
    d["VolR"] = volume / volume.rolling(20).mean()
    d["ROC"] = (close / close.shift(10) - 1) * 100
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    d["MACD"] = macd - macd.ewm(span=9, adjust=False).mean()
    
    prev_close = close.shift(1)
    tr = pd.concat([high-low, (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    up, down = high.diff(), -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0), index=d.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0), index=d.index)
    
    atr = wilder_average(tr, 14)
    plus_sm = wilder_average(plus_dm, 14)
    minus_sm = wilder_average(minus_dm, 14)
    plus_di = 100 * plus_sm / atr
    minus_di = 100 * minus_sm / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    d["ADX"] = wilder_average(dx, 14)
    
    return d.dropna(subset=["MA50","MA200","VolR","ROC","MACD","ADX"])

# ---------- SETUP ----------
VN_TZ = pytz.timezone(TIMEZONE)
now = datetime.now(VN_TZ)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
state_path = os.path.join(BASE_DIR, STATE_FILE)
log_path = os.path.join(BASE_DIR, LOG_FILE)

print(f"===== {TELEGRAM_TITLE} - {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")

# Kiem tra che do thu cong
is_manual = os.environ.get("IS_MANUAL", "false").lower() == "true"
if is_manual:
    print("[CHE DO THU CONG] Bo qua kiem tra gio giao dich.")

if now.weekday() >= 5 and not is_manual:
    print("Cuoi tuan - bo qua"); sys.exit(0)

current_time = now.hour * 100 + now.minute
if (current_time < 900 or current_time > 1500) and not is_manual:
    print(f"[{now.strftime('%H:%M')}] Ngoai gio giao dich. Bo qua."); sys.exit(0)

# ---------- LOAD STATE ----------
state = {"positions": {}, "cash": CAPITAL_INITIAL, "peak_equity": CAPITAL_INITIAL, "last_signals": {}, "last_run": None}
if os.path.exists(state_path):
    try:
        with open(state_path) as f:
            loaded = json.load(f)
            for k, v in loaded.items(): state[k] = v
    except Exception as e:
        print(f"[state load fail] {e}")

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

def check_signal(df, p):
    r = df.iloc[-1]
    conds = [
        r["VolR"] > p["volr"], r["ROC"] > p["roc"], r["MACD"] > p["macd"], r["ADX"] > p["adx"]
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
    n = 0; cur = d1
    while cur.date() < d2.date():
        cur += timedelta(days=1)
        if cur.weekday() < 5: n += 1
    return n

# ---------- MAIN LOOP ----------
buy_dcm, sell_dcm, buy_gvr, sell_gvr = [], [], [], []
price_cache = {}

for rule_name, basket in [("DCM", DCM_BASKET), ("GVR", GVR_BASKET)]:
    print(f"--- Rule {rule_name} ({len(basket)} ma) ---")
    for tk in basket:
        key = f"{tk}_{rule_name}"
        try:
            df_raw = get_intraday_data(tk, days=400)
            if len(df_raw) < 50:
                time.sleep(DELAY_BETWEEN_TICKERS); continue
            df = add_indicators(df_raw)
            
            sig, r = check_signal(df, RULE_PARAMS[rule_name])
            price_cache[tk] = r["Close"]
            prev = state["last_signals"].get(key, False)
            pos = state["positions"].get(key)

            if sig and not prev and not pos:
                size, tier = size_from_tier(r["VolR"])
                if len(state["positions"]) < MAX_POSITIONS and state["cash"] >= size:
                    state["cash"] -= size
                    state["positions"][key] = {
                        "entry_date": str(now.date()), "entry_price": r["Close"],
                        "size": size, "tier": tier, "volr": round(r["VolR"], 2),
                    }
                    if rule_name == "DCM": buy_dcm.append((tk, tier, size))
                    else: buy_gvr.append((tk, tier, size))
                    print(f"  [{tk}] BUY {tier} size={size/1e6:.0f}tr volR={r['VolR']:.2f}")
            elif (not sig) and prev and pos:
                hold = business_days_between(pos["entry_date"], now)
                if hold >= RULE_PARAMS[rule_name]["hold"]:
                    ret = r["Close"] / pos["entry_price"]
                    state["cash"] += pos["size"] * ret
                    if rule_name == "DCM": sell_dcm.append((tk, ret - 1))
                    else: sell_gvr.append((tk, ret - 1))
                    print(f"  [{tk}] SELL hold={hold} ret={(ret-1)*100:+.2f}%")
                    del state["positions"][key]
            else:
                print(f"  [{tk}] close={r['Close']:.2f} ADX={r['ADX']:.1f} VolR={r['VolR']:.2f} sig={sig}")

            state["last_signals"][key] = sig
            time.sleep(DELAY_BETWEEN_TICKERS)
        except Exception as e:
            print(f"  [{tk}] ERR: {str(e)[:100]}")
            time.sleep(DELAY_BETWEEN_TICKERS)

# ---------- EQUITY & DD ----------
mtm = state["cash"]
for key, pos in state["positions"].items():
    tk = key.split("_")[0]
    if tk in price_cache: mtm += pos["size"] * (price_cache[tk] / pos["entry_price"])
    else: mtm += pos["size"]

peak = max(state["peak_equity"], mtm)
dd = (mtm - peak) / peak * 100 if peak > 0 else 0
state["peak_equity"] = peak
state["last_run"] = str(now)

print(f"MTM: {mtm/1e9:.4f} ty | Cash: {state['cash']/1e9:.4f} ty | DD: {dd:.2f}%")

with open(state_path, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

# ---------- TELEGRAM ----------
lines = [f"<b>{TELEGRAM_TITLE}</b> - {now.strftime('%Y-%m-%d %H:%M')}"]
if buy_dcm or sell_dcm or buy_gvr or sell_gvr:
    if buy_dcm:
        lines.append("<b>DCM BUY:</b>")
        for tk, tier, sz in buy_dcm: lines.append(f"  + {tk} - Tier {tier} - {sz/1e6:.0f}tr")
    if sell_dcm:
        lines.append("<b>DCM SELL:</b>")
        for tk, ret in sell_dcm: lines.append(f"  - {tk} - {ret*100:+.2f}%")
    if buy_gvr:
        lines.append("<b>GVR BUY:</b>")
        for tk, tier, sz in buy_gvr: lines.append(f"  + {tk} - Tier {tier} - {sz/1e6:.0f}tr")
    if sell_gvr:
        lines.append("<b>GVR SELL:</b>")
        for tk, ret in sell_gvr: lines.append(f"  - {tk} - {ret*100:+.2f}%")
    lines.append(f"\nMTM: {mtm/1e9:.4f} ty | Peak: {peak/1e9:.4f} ty | DD: {dd:+.2f}%")
    send_telegram("\n".join(lines))
else:
    msg = f"<b>{TELEGRAM_TITLE}</b> - {now.strftime('%H:%M')}\nKhong co tin hieu moi.\nMTM: {mtm/1e9:.4f} ty | Cash: {state['cash']/1e9:.4f} ty"
    send_telegram(msg)
    print("Khong co tin hieu moi.")

print(f"===== DONE - DCM:{len(buy_dcm)} GVR:{len(buy_gvr)} =====")
ST5 HIEP-SCAN - VNDirect API (Chuan TradingView, ho tro IS_MANUAL)
"""
import os, sys, json, time, csv
from datetime import datetime, timedelta
import pytz, requests
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_hiep_scan import (
    DCM_BASKET, GVR_BASKET, RULE_PARAMS,
    TIER_A_VOLR, TIER_B_VOLR, SIZE_A, SIZE_B, SIZE_C,
    CAPITAL_INITIAL, MAX_POSITIONS, DD_ALERT_THRESHOLD,
    TIMEZONE, STATE_FILE, LOG_FILE,
    TELEGRAM_TITLE, DELAY_BETWEEN_TICKERS,
)

# ---------- DATA PULLING (VNDIRECT) ----------
def get_intraday_data(ticker, days=400):
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
    except Exception as e:
        print(f" [{ticker}] Loi API VNDirect: {str(e)[:50]}")
    
    print(f" [{ticker}] FAIL to pull data.")
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

def add_indicators(df):
    d = df.copy()
    close, high, low, volume = d["Close"], d["High"], d["Low"], d["Volume"]
    d["MA50"] = close.rolling(50).mean()
    d["MA200"] = close.rolling(200).mean()
    d["VolR"] = volume / volume.rolling(20).mean()
    d["ROC"] = (close / close.shift(10) - 1) * 100
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    d["MACD"] = macd - macd.ewm(span=9, adjust=False).mean()
    
    prev_close = close.shift(1)
    tr = pd.concat([high-low, (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    up, down = high.diff(), -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0), index=d.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0), index=d.index)
    
    atr = wilder_average(tr, 14)
    plus_sm = wilder_average(plus_dm, 14)
    minus_sm = wilder_average(minus_dm, 14)
    plus_di = 100 * plus_sm / atr
    minus_di = 100 * minus_sm / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    d["ADX"] = wilder_average(dx, 14)
    
    return d.dropna(subset=["MA50","MA200","VolR","ROC","MACD","ADX"])

# ---------- SETUP ----------
VN_TZ = pytz.timezone(TIMEZONE)
now = datetime.now(VN_TZ)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
state_path = os.path.join(BASE_DIR, STATE_FILE)
log_path = os.path.join(BASE_DIR, LOG_FILE)

print(f"===== {TELEGRAM_TITLE} - {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")

# Kiem tra che do thu cong
is_manual = os.environ.get("IS_MANUAL", "false").lower() == "true"
if is_manual:
    print("[CHE DO THU CONG] Bo qua kiem tra gio giao dich.")

if now.weekday() >= 5 and not is_manual:
    print("Cuoi tuan - bo qua"); sys.exit(0)

current_time = now.hour * 100 + now.minute
if (current_time < 900 or current_time > 1500) and not is_manual:
    print(f"[{now.strftime('%H:%M')}] Ngoai gio giao dich. Bo qua."); sys.exit(0)

# ---------- LOAD STATE ----------
state = {"positions": {}, "cash": CAPITAL_INITIAL, "peak_equity": CAPITAL_INITIAL, "last_signals": {}, "last_run": None}
if os.path.exists(state_path):
    try:
        with open(state_path) as f:
            loaded = json.load(f)
            for k, v in loaded.items(): state[k] = v
    except Exception as e:
        print(f"[state load fail] {e}")

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

def check_signal(df, p):
    r = df.iloc[-1]
    conds = [
        r["VolR"] > p["volr"], r["ROC"] > p["roc"], r["MACD"] > p["macd"], r["ADX"] > p["adx"]
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
    n = 0; cur = d1
    while cur.date() < d2.date():
        cur += timedelta(days=1)
        if cur.weekday() < 5: n += 1
    return n

# ---------- MAIN LOOP ----------
buy_dcm, sell_dcm, buy_gvr, sell_gvr = [], [], [], []
price_cache = {}

for rule_name, basket in [("DCM", DCM_BASKET), ("GVR", GVR_BASKET)]:
    print(f"--- Rule {rule_name} ({len(basket)} ma) ---")
    for tk in basket:
        key = f"{tk}_{rule_name}"
        try:
            df_raw = get_intraday_data(tk, days=400)
            if len(df_raw) < 50:
                time.sleep(DELAY_BETWEEN_TICKERS); continue
            df = add_indicators(df_raw)
            
            sig, r = check_signal(df, RULE_PARAMS[rule_name])
            price_cache[tk] = r["Close"]
            prev = state["last_signals"].get(key, False)
            pos = state["positions"].get(key)

            if sig and not prev and not pos:
                size, tier = size_from_tier(r["VolR"])
                if len(state["positions"]) < MAX_POSITIONS and state["cash"] >= size:
                    state["cash"] -= size
                    state["positions"][key] = {
                        "entry_date": str(now.date()), "entry_price": r["Close"],
                        "size": size, "tier": tier, "volr": round(r["VolR"], 2),
                    }
                    if rule_name == "DCM": buy_dcm.append((tk, tier, size))
                    else: buy_gvr.append((tk, tier, size))
                    print(f"  [{tk}] BUY {tier} size={size/1e6:.0f}tr volR={r['VolR']:.2f}")
            elif (not sig) and prev and pos:
                hold = business_days_between(pos["entry_date"], now)
                if hold >= RULE_PARAMS[rule_name]["hold"]:
                    ret = r["Close"] / pos["entry_price"]
                    state["cash"] += pos["size"] * ret
                    if rule_name == "DCM": sell_dcm.append((tk, ret - 1))
                    else: sell_gvr.append((tk, ret - 1))
                    print(f"  [{tk}] SELL hold={hold} ret={(ret-1)*100:+.2f}%")
                    del state["positions"][key]
            else:
                print(f"  [{tk}] close={r['Close']:.2f} ADX={r['ADX']:.1f} VolR={r['VolR']:.2f} sig={sig}")

            state["last_signals"][key] = sig
            time.sleep(DELAY_BETWEEN_TICKERS)
        except Exception as e:
            print(f"  [{tk}] ERR: {str(e)[:100]}")
            time.sleep(DELAY_BETWEEN_TICKERS)

# ---------- EQUITY & DD ----------
mtm = state["cash"]
for key, pos in state["positions"].items():
    tk = key.split("_")[0]
    if tk in price_cache: mtm += pos["size"] * (price_cache[tk] / pos["entry_price"])
    else: mtm += pos["size"]

peak = max(state["peak_equity"], mtm)
dd = (mtm - peak) / peak * 100 if peak > 0 else 0
state["peak_equity"] = peak
state["last_run"] = str(now)

print(f"MTM: {mtm/1e9:.4f} ty | Cash: {state['cash']/1e9:.4f} ty | DD: {dd:.2f}%")

with open(state_path, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

# ---------- TELEGRAM ----------
lines = [f"<b>{TELEGRAM_TITLE}</b> - {now.strftime('%Y-%m-%d %H:%M')}"]
if buy_dcm or sell_dcm or buy_gvr or sell_gvr:
    if buy_dcm:
        lines.append("<b>DCM BUY:</b>")
        for tk, tier, sz in buy_dcm: lines.append(f"  + {tk} - Tier {tier} - {sz/1e6:.0f}tr")
    if sell_dcm:
        lines.append("<b>DCM SELL:</b>")
        for tk, ret in sell_dcm: lines.append(f"  - {tk} - {ret*100:+.2f}%")
    if buy_gvr:
        lines.append("<b>GVR BUY:</b>")
        for tk, tier, sz in buy_gvr: lines.append(f"  + {tk} - Tier {tier} - {sz/1e6:.0f}tr")
    if sell_gvr:
        lines.append("<b>GVR SELL:</b>")
        for tk, ret in sell_gvr: lines.append(f"  - {tk} - {ret*100:+.2f}%")
    lines.append(f"\nMTM: {mtm/1e9:.4f} ty | Peak: {peak/1e9:.4f} ty | DD: {dd:+.2f}%")
    send_telegram("\n".join(lines))
else:
    msg = f"<b>{TELEGRAM_TITLE}</b> - {now.strftime('%H:%M')}\nKhong co tin hieu moi.\nMTM: {mtm/1e9:.4f} ty | Cash: {state['cash']/1e9:.4f} ty"
    send_telegram(msg)
    print("Khong co tin hieu moi.")

print(f"===== DONE - DCM:{len(buy_dcm)} GVR:{len(buy_gvr)} =====") 
