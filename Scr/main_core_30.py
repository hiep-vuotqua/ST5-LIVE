"""CORE-30 engine — 3 cron/ngày (11:00, 13:30, 14:00 VN)."""

import os
import json
import time
from datetime import datetime
import pytz
import pandas as pd
import requests

from config_core_30 import (
    CORE_30, VOLUME_RATIO_MIN, ROC10_MIN, MACD_HIST_MIN, ADX14_MIN,
    USE_MA200, USE_MA50, MIN_HOLD_DAYS, TIMEZONE, STATE_FILE,
    TELEGRAM_TITLE, FEE_PER_ROUND, DELAY_BETWEEN_TICKERS
)
from data_core_30 import get_intraday_data
from indicators import add_v14_indicators

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


def load_state():
    abs_path = os.path.abspath(STATE_FILE)
    print(f"  [load_state] Reading: {abs_path}")
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"  [load_state] File không tồn tại, trả về rỗng")
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    abs_path = os.path.abspath(STATE_FILE)
    print(f"  [save_state] Writing: {abs_path}")
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)


def core_signal(df):
    conds = (
        (df["VolumeRatio"] > VOLUME_RATIO_MIN) &
        (df["ROC10"]       > ROC10_MIN) &
        (df["MACD_Hist"]   > MACD_HIST_MIN) &
        (df["ADX14"]       > ADX14_MIN)
    )
    if USE_MA200:
        conds = conds & (df["Close"] > df["MA200"])
    if USE_MA50:
        conds = conds & (df["Close"] > df["MA50"])
    return conds


def get_session(now):
    h, m = now.hour, now.minute
    if h < 12:
        return "SÁNG"        # 11:00
    if h < 14:
        return "CHIỀU"       # 13:30
    return "CUỐI PHIÊN"      # 14:00


def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram chưa cấu hình")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"[{TELEGRAM_TITLE}] {msg}",
            "parse_mode": "HTML"
        }, timeout=10)
        if r.status_code != 200:
            print(f"[WARN] Telegram HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")


def process_ticker(ticker, state, tz, session, now):
    try:
        df = get_intraday_data(ticker, days=50a0)
    except Exception as e:
        print(f"  [{ticker}] ERROR data: {e}")
        return state

    if df is None or len(df) < 250:
        print(f"  [{ticker}] SKIP — {len(df)} nến (cần 250)")
        return state

    df["MA50"]  = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    df = add_v14_indicators(df).dropna().reset_index(drop=True)

    if len(df) == 0:
        print(f"  [{ticker}] SKIP — dropna hết data")
        return state

    df["Signal"] = core_signal(df)

    last = df.iloc[-1]
    today = str(pd.to_datetime(last["Date"]).date())

    # Schema state mới — dùng setdefault để tương thích state cũ
    t_state = state.get(ticker, {
        "in_position": False,
        "buy_date": None,
        "buy_price": None,
        "alerted_buy_dates": [],
        "alerted_sell_dates": [],
    })
    t_state.setdefault("alerted_buy_dates", [])
    t_state.setdefault("alerted_sell_dates", [])

    in_pos = t_state["in_position"]
    signal_now = bool(last["Signal"])

    print(f"  [{ticker}] {today} {session} | C={last['Close']:.2f} | "
          f"VolR={last['VolumeRatio']:.2f} | ROC10={last['ROC10']:.2f} | "
          f"MACD={last['MACD_Hist']:.3f} | ADX={last['ADX14']:.1f} | "
          f"sig={signal_now} | pos={in_pos}")

    tag = {"SÁNG": "🌅", "CHIỀU": "🌤", "CUỐI PHIÊN": "🔔"}[session]
    ts = now.strftime("%H:%M")

    if not in_pos:
        if signal_now and today not in t_state["alerted_buy_dates"]:
            t_state["in_position"] = True
            t_state["buy_date"]    = today
            t_state["buy_price"]   = float(last["Close"])
            t_state["alerted_buy_dates"] = (t_state["alerted_buy_dates"] + [today])[-10:]

            msg = (
                f"{tag} <b>MUA {ticker}</b> [{session}] {ts}\n"
                f"Giá: {last['Close']:.2f} | Ngày: {today}\n"
                f"VolR: {last['VolumeRatio']:.2f} | "
                f"ROC10: {last['ROC10']:.2f}% | "
                f"MACD: {last['MACD_Hist']:.3f} | "
                f"ADX: {last['ADX14']:.1f}\n"
                f"\n⚠️ Giá có thể đổi đến 15:00. Check giá sàn trước khi đặt lệnh."
            )
            send_telegram(msg)
            print(f"  [{ticker}] >>> BUY ALERT @ {last['Close']:.2f}")
        elif signal_now:
            print(f"  [{ticker}] đã alert MUA hôm nay, bỏ qua")
    else:
        buy_dt = pd.to_datetime(t_state["buy_date"]).date()
        hold_days = (pd.to_datetime(today).date() - buy_dt).days

        if ((not signal_now) and hold_days >= MIN_HOLD_DAYS
                and today not in t_state["alerted_sell_dates"]):
            buy_price = t_state["buy_price"]
            ret = (last["Close"] / buy_price - 1) * 100
            ret_net = ret - FEE_PER_ROUND

            t_state["in_position"] = False
            t_state["buy_date"]    = None
            t_state["buy_price"]   = None
            t_state["alerted_sell_dates"] = (t_state["alerted_sell_dates"] + [today])[-10:]

            msg = (
                f"{tag} <b>BÁN {ticker}</b> [{session}] {ts}\n"
                f"Giá: {last['Close']:.2f} | Mua: {buy_price:.2f}\n"
                f"Return: {ret:+.2f}% (net {ret_net:+.2f}%)\n"
                f"Hold: {hold_days} ngày | Ngày: {today}\n"
                f"\n⚠️ Giá có thể đổi đến 15:00."
            )
            send_telegram(msg)
            print(f"  [{ticker}] >>> SELL ALERT @ {last['Close']:.2f} | ret {ret:+.2f}%")
        else:
            print(f"  [{ticker}] HOLD | {hold_days} ngày | sig={signal_now}")

    state[ticker] = t_state
    return state


def main():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    session = get_session(now)
    print(f"===== ST5 CORE-30 [{session}] — {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")

    if now.weekday() >= 5:
        print("Cuối tuần — bỏ qua")
        return

    state = load_state()

    n_buy = n_sell = 0
    for i, ticker in enumerate(CORE_30, 1):
        old_pos = state.get(ticker, {}).get("in_position", False)
        state = process_ticker(ticker, state, tz, session, now)
        new_pos = state.get(ticker, {}).get("in_position", False)
        if not old_pos and new_pos: n_buy += 1
        if old_pos and not new_pos: n_sell += 1
        if i < len(CORE_30):
            time.sleep(DELAY_BETWEEN_TICKERS)

    save_state(state)
    print(f"\n===== DONE [{session}] — BUY: {n_buy}, SELL: {n_sell}, Total: {len(CORE_30)} =====")


if __name__ == "__main__":
    main() 
