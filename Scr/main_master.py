"""
ST5 MASTER — chạy 7 rule, gộp signal, gửi 1 tin Telegram
Đã fix: Chống mua trùng mã (dồn tiền vào 1 mã), thêm Heartbeat.
"""
import os, sys, json, time, csv
from datetime import datetime, timedelta
import pytz, requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_master import (
    RULES, POSITION_SIZE, MAX_POSITIONS, CAPITAL_INITIAL,
    TIMEZONE, STATE_FILE, LOG_FILE, TELEGRAM_TITLE, DELAY_BETWEEN_TICKERS,
)
from data_master import get_intraday_data
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
state = {"positions": {}, "last_signals": {}, "cash": CAPITAL_INITIAL, "last_run": None}
if os.path.exists(state_path):
    try:
        with open(state_path) as f:
            loaded = json.load(f)
            for k in state: 
                if k in loaded: state[k] = loaded[k]
    except Exception as e:
        print(f"[state load fail] {e}")

# Cache data theo ticker để không pull trùng
ticker_cache = {}

def get_cached_data(tk, days=400):
    if tk in ticker_cache:
        return ticker_cache[tk]
    df = get_intraday_data(tk, days=days)
    ticker_cache[tk] = df
    return df

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

def business_days_since(date_str, now_dt):
    d1 = datetime.strptime(date_str, "%Y-%m-%d")
    n = 0; cur = d1
    while cur.date() < now_dt.date():
        cur += timedelta(days=1)
        if cur.weekday() < 5: n += 1
    return n

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

# ============ QUÉT TẤT CẢ RULES ============
signal_map = {}   # ticker -> list of dicts

for rule_name, rule in RULES.items():
    print(f"\n--- {rule_name} ({len(rule['tickers'])} mã) ---")
    for tk in rule["tickers"]:
        key = f"{tk}__{rule_name}"
        try:
            df = get_cached_data(tk)
            if len(df) == 0: continue
            sig, r = check_signal(df, rule)
            if sig is None: continue
            
            prev = state["last_signals"].get(key, False)
            pos = state["positions"].get(key)
            
            if sig and not prev and not pos:
                # FIX LỖI MUA TRÙNG MÃ: Nếu mã này đã nằm trong danh mục (bất kể rule nào) thì bỏ qua
                already_held = any(k.startswith(f"{tk}__") for k in state["positions"])
                
                if already_held:
                    print(f"  [{tk}] BUY signal ({rule_name}) but ALREADY HELD another rule — skipped")
                    state["last_signals"][key] = sig
                    continue
                
                if len(state["positions"]) < MAX_POSITIONS and state["cash"] >= POSITION_SIZE:
                    state["cash"] -= POSITION_SIZE
                    state["positions"][key] = {
                        "entry_date": str(now.date()),
                        "entry_price": r["Close"],
                        "size": POSITION_SIZE,
                        "volr": round(r["VolumeRatio"], 2),
                        "adx": round(r["ADX14"], 2),
                    }
                    signal_map.setdefault(tk, []).append({
                        "rule": rule_name, "action": "BUY",
                        "volr": r["VolumeRatio"], "adx": r["ADX14"], "roc": r["ROC10"],
                    })
                    print(f"  [{tk}] BUY {rule_name} volR={r['VolumeRatio']:.2f} ADX={r['ADX14']:.1f}")
                else:
                    print(f"  [{tk}] BUY signal but full/cash — skipped")
            elif (not sig) and prev and pos:
                hold = business_days_since(pos["entry_date"], now)
                if hold >= rule["mh"]:
                    ret = r["Close"] / pos["entry_price"]
                    proceeds = pos["size"] * ret
                    state["cash"] += proceeds
                    signal_map.setdefault(tk, []).append({
                        "rule": rule_name, "action": "SELL",
                        "ret": ret - 1, "hold": hold,
                    })
                    print(f"  [{tk}] SELL hold={hold} ret={(ret-1)*100:+.2f}%")
                    del state["positions"][key]
            
            state["last_signals"][key] = sig
            time.sleep(DELAY_BETWEEN_TICKERS)
        except Exception as e:
            print(f"  [{tk}] ERR: {str(e)[:100]}")
            time.sleep(DELAY_BETWEEN_TICKERS)

state["last_run"] = str(now)

# ============ TỔNG HỢP ============
buys = {tk: sigs for tk, sigs in signal_map.items() if any(s["action"]=="BUY" for s in sigs)}
sells = {tk: sigs for tk, sigs in signal_map.items() if any(s["action"]=="SELL" for s in sigs)}

# Lưu State
with open(state_path, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

# ============ TELEGRAM ============
if buys or sells:
    lines = [f"📊 <b>{TELEGRAM_TITLE}</b> — {now.strftime('%Y-%m-%d %H:%M')}"]
    
    if buys:
        lines.append(f"\n🟢 <b>MUA ({len(buys)}):</b>")
        for tk, sigs in sorted(buys.items(), key=lambda x: -len([s for s in x[1] if s["action"]=="BUY"])):
            buy_sigs = [s for s in sigs if s["action"]=="BUY"]
            n = len(buy_sigs)
            strength = "🔥" * min(n, 3)
            rules_str = " + ".join(s["rule"] for s in buy_sigs)
            volr = buy_sigs[0]["volr"]; adx = buy_sigs[0]["adx"]; roc = buy_sigs[0]["roc"]
            lines.append(f"  {strength} <b>{tk}</b> — {rules_str}")
            lines.append(f"     VolR={volr:.2f} ADX={adx:.1f} ROC={roc:.1f}")
    
    if sells:
        lines.append(f"\n🔴 <b>BÁN ({len(sells)}):</b>")
        for tk, sigs in sells.items():
            sell_sigs = [s for s in sigs if s["action"]=="SELL"]
            for s in sell_sigs:
                lines.append(f"  • {tk} — {s['rule']} (hold {s['hold']}d, {s['ret']*100:+.2f}%)")
    
    lines.append(f"\n💰 Cash: {state['cash']/1e9:.4f} tỷ | Pos: {len(state['positions'])}")
    send_telegram("\n".join(lines))
else:
    # HEARTBEAT: Báo cáo trạng thái nếu không có tín hiệu
    msg = f"🤖 <b>{TELEGRAM_TITLE}</b> — {now.strftime('%H:%M')}\n"
    msg += f"Trạng thái: Không có tín hiệu mới.\n"
    msg += f"💰 Cash: {state['cash']/1e9:.4f} tỷ | Đang giữ: {len(state['positions'])} mã"
    send_telegram(msg)
    print("\nKhông có tín hiệu mới — Đã gửi tin nhắn Heartbeat.")

print(f"\n===== DONE — {len(buys)} BUY signals, {len(sells)} SELL signals =====")
