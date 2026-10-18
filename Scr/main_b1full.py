"""
Logic bot ST5-B1FULL — Merge-12 + Trail 10%.
Chạy 10:00, 11:00, 13:40, 14:10 (T2-T6) qua cron-job.org.
Signal: bar cuối (T-1) → entry ATC hôm nay.
Exit: hold đủ mh ngày HOẶC trail trigger (close T-1 <= peak*0.9).
"""

import os, sys, json, time, requests
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from config_b1full import B1FULL_RULES, CAPITAL_ALLOC, TRAIL_PCT, TELEGRAM_PREFIX

# ---------- INDICATORS ----------
# Base indicators.py của repo (nếu có) — dùng làm nền
try:
    from indicators import add_v14_indicators as _base_ind
except ImportError:
    _base_ind = None

def _calc_adx(df, period=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    up = h.diff(); dn = -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    pdi = pd.Series(pdm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr * 100
    mdi = pd.Series(mdm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr * 100
    dx = (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan) * 100
    return dx.ewm(alpha=1/period, adjust=False).mean()

def prepare(df):
    """
    Enrich DataFrame với tất cả cột cần cho signal check:
    VolR, ROC10, MACD_Hist, ADX14, MA50, MA200.
    Dùng indicators.py của repo nếu có, sau đó fill missing columns.
    """
    d = df.copy()
    # 1) Gọi base indicators.py (nếu import được)
    if _base_ind is not None:
        try:
            d = _base_ind(d)
        except Exception as e:
            print(f"    [warn] base indicators fail: {e}")
    # 2) Đảm bảo từng cột cần thiết có mặt
    if "VolR" not in d.columns:
        if "VolumeRatio" in d.columns:
            d["VolR"] = d["VolumeRatio"]
        else:
            d["VolR"] = d["Volume"] / d["Volume"].rolling(20).mean()
    if "ROC10" not in d.columns:
        d["ROC10"] = d["Close"].pct_change(10) * 100.0
    if "MACD_Hist" not in d.columns:
        e12 = d["Close"].ewm(span=12, adjust=False).mean()
        e26 = d["Close"].ewm(span=26, adjust=False).mean()
        m = e12 - e26
        d["MACD_Hist"] = m - m.ewm(span=9, adjust=False).mean()
    if "ADX14" not in d.columns:
        d["ADX14"] = _calc_adx(d)
    if "MA50" not in d.columns:
        d["MA50"] = d["Close"].rolling(50).mean()
    if "MA200" not in d.columns:
        d["MA200"] = d["Close"].rolling(200).mean()
    return d

# ---------- PULL DATA ----------
try:
    from data_master import pull_daily
except ImportError:
    from vnstock import Quote
    def pull_daily(ticker, start="2018-01-01", end=None):
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")
        for src in ["KBS", "VCI"]:
            try:
                q = Quote(source=src, symbol=ticker)
                df = q.history(start=start, end=end, interval="1D")
                if df is None or len(df) == 0:
                    continue
                df.columns = [str(c).strip().lower() for c in df.columns]
                rn = {"time":"Date","date":"Date","open":"Open","high":"High",
                      "low":"Low","close":"Close","volume":"Volume"}
                df = df.rename(columns={k:v for k,v in rn.items() if k in df.columns})
                df = df[["Date","Open","High","Low","Close","Volume"]].copy()
                df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
                for c in ["Open","High","Low","Close","Volume"]:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                df = df.dropna().drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
                time.sleep(3)
                return df
            except Exception:
                time.sleep(5)
                continue
        return pd.DataFrame()

# ---------- PATHS ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "..", "data", "live_state_b1full.json")
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

# ---------- TELEGRAM ----------
def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat  = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("[WARN] Thiếu TELEGRAM secrets")
        print(msg)
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=20,
        )
        if r.status_code != 200:
            print(f"[WARN] Telegram {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[WARN] Telegram exception: {e}")

# ---------- STATE ----------
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)

# ---------- SIGNAL ----------
def check_signal(row, cfg):
    for col in ["ADX14", "VolR", "ROC10"]:
        if col not in row.index or pd.isna(row[col]):
            return False
    if row["ADX14"] < cfg["adx"]: return False
    if row["VolR"]  < cfg["volr"]: return False
    if row["ROC10"] < cfg["roc"]: return False
    if cfg["macd"] is not None:
        if "MACD_Hist" not in row.index or pd.isna(row["MACD_Hist"]):
            return False
        if row["MACD_Hist"] <= cfg["macd"]:
            return False
    if cfg["ma50"]:
        if "MA50" not in row.index or pd.isna(row["MA50"]):
            return False
        if row["Close"] <= row["MA50"]:
            return False
    if cfg["ma200"]:
        if "MA200" not in row.index or pd.isna(row["MA200"]):
            return False
        if row["Close"] <= row["MA200"]:
            return False
    return True

# ---------- MAIN ----------
def main():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    state = load_state()
    nav = CAPITAL_ALLOC["nav"]
    size_vnd = nav * CAPITAL_ALLOC["size_pct"]
    max_pos = CAPITAL_ALLOC["max_positions"]

    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] B1FULL — state {len(state)}/{max_pos} | TRAIL={TRAIL_PCT}%")

    buys, sells, errors = [], [], []

    for ticker, cfg in B1FULL_RULES.items():
        print(f"  pull {ticker}...", end=" ", flush=True)
        df = pull_daily(ticker, start="2020-01-01")
        if df is None or len(df) < 210:
            print("no data / <210 rows")
            errors.append(ticker)
            continue
        df = prepare(df)
        last = df.iloc[-1]

        # ===== ĐANG CÓ POSITION =====
        if ticker in state:
            pos = state[ticker]
            hold_days = (pd.Timestamp(today_str) - pd.Timestamp(pos["entry_date"])).days

            old_peak = pos.get("peak_price", pos["entry_px"])
            new_peak = max(old_peak, float(last["Close"]))
            pos["peak_price"] = new_peak

            trail_line = new_peak * (1 - TRAIL_PCT / 100)
            exit_reason = None
            if float(last["Close"]) <= trail_line:
                exit_reason = "TRAIL"
            elif hold_days >= cfg["mh"]:
                exit_reason = "HOLD"

            if exit_reason:
                exit_px = float(last["Close"])
                ret = (exit_px / pos["entry_px"] - 1) * 100
                pnl = size_vnd * ret / 100
                sells.append({
                    "ticker": ticker, "variant": pos.get("variant",""),
                    "hold": hold_days, "ret": ret, "pnl": pnl,
                    "reason": exit_reason, "peak": new_peak,
                })
                del state[ticker]
                print(f"{exit_reason} (hold {hold_days}d, {ret:+.2f}%)")
                continue

            print(f"HOLD ({hold_days}/{cfg['mh']}d, peak={new_peak:.1f})")
            continue

        # ===== KHÔNG CÓ POSITION — check MUA =====
        if len(state) >= max_pos:
            print(f"skip (full {max_pos})")
            continue
        if check_signal(last, cfg):
            entry_px = float(last["Close"])
            state[ticker] = {
                "entry_date":  today_str,
                "entry_px":    entry_px,
                "peak_price":  entry_px,
                "variant":     cfg["variant"],
                "adx":         float(last["ADX14"]),
                "volr":        float(last["VolR"]),
                "roc":         float(last["ROC10"]),
                "sector":      cfg.get("sector",""),
            }
            buys.append({
                "ticker": ticker, "variant": cfg["variant"],
                "adx": float(last["ADX14"]), "volr": float(last["VolR"]),
                "roc": float(last["ROC10"]), "size_vnd": size_vnd,
            })
            print(f"MUA (ADX={last['ADX14']:.1f} VolR={last['VolR']:.2f} ROC={last['ROC10']:.2f})")
        else:
            print("no signal")

    save_state(state)

    # ===== TELEGRAM =====
    lines = [
        f"📊 <b>{TELEGRAM_PREFIX}</b> — {now.strftime('%Y-%m-%d %H:%M')}",
        f"<i>Trail {TRAIL_PCT:.0f}% | {len(B1FULL_RULES)} mã</i>",
    ]
    if buys:
        lines.append(f"🟢 <b>MUA ({len(buys)})</b>:")
        for b in buys:
            lines.append(
                f"   • <b>{b['ticker']}</b> — {b['variant']} ({b['size_vnd']/1e6:.0f}tr) "
                f"VolR={b['volr']:.2f} ADX={b['adx']:.1f} ROC={b['roc']:.2f}"
            )
    if sells:
        lines.append(f"🔴 <b>BÁN ({len(sells)})</b>:")
        for s in sells:
            emoji = "🟢" if s['ret'] > 0 else "🔴"
            tag = "TRAIL" if s['reason'] == "TRAIL" else f"{s['hold']}d"
            lines.append(
                f"   {emoji} <b>{s['ticker']}</b> — {tag} "
                f"{s['ret']:+.2f}% ({s['pnl']/1e6:+.1f}tr)"
            )
    if not buys and not sells:
        lines.append("⏸ Không có signal")
    if errors:
        lines.append(f"⚠️ Lỗi pull: {', '.join(errors)}")

    cash_used = len(state) * size_vnd
    lines.append(
        f"💰 Pos: {len(state)}/{max_pos} | "
        f"Deployed: {cash_used/1e9:.2f} tỷ | "
        f"Cash: {(nav-cash_used)/1e9:.2f} tỷ"
    )

    msg = "\n".join(lines)
    print("\n" + msg)
    send_telegram(msg)

if __name__ == "__main__":
    main()
