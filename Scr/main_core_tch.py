# Scr/main_core_tch.py
# Engine LIVE cho CORE-TCH — 34 mã
# Đọc config từ config_core_tch.py

import os
import json
import time
from datetime import datetime
import pytz
import pandas as pd
import numpy as np
import requests

from config_core_tch import (
    CORE_TCH, VOLUME_RATIO_MIN, ROC10_MIN, MACD_HIST_MIN, ADX14_MIN,
    MIN_HOLD_DAYS, MORNING_START, MORNING_END, AFTERNOON_START, AFTERNOON_END,
    TIMEZONE, STATE_FILE, TELEGRAM_TITLE, FEE_PER_ROUND, DELAY_BETWEEN_TICKERS
)
from data import get_intraday_data
from indicators import add_v14_indicators

# ===== TELEGRAM =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ===== STATE =====
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)

# ===== SIGNAL =====
def core_tch_signal(df):
    return (
        (df["VolumeRatio"]  >= VOLUME_RATIO_MIN) &
        (df["ROC10"]     >= ROC10_MIN) &
        (df["MACD_Hist"] >= MACD_HIST_MIN) &
        (df["ADX14"]     >= ADX14_MIN)
    )

# ===== TELEGRAM =====
def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram token/chat_id chưa cấu hình")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"[{TELEGRAM_TITLE}] {msg}",
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

# ===== XỬ LÝ 1 MÃ =====
def process_ticker(ticker, state, tz):
    try:
        df = get_intraday_data(ticker, days=20)
    except Exception as e:
        print(f"  [{ticker}] ERROR data: {e}")
        return state

    if df is None or len(df) < 30:
        print(f"  [{ticker}] SKIP — không đủ dữ liệu")
        return state

    df = add_v14_indicators(df)
    df["Signal"] = core_tch_signal(df)

    last = df.iloc[-1]
    last_dt = pd.to_datetime(last["Date"])
    if last_dt.tz is None:
        last_dt = last_dt.tz_localize(tz)
    else:
        last_dt = last_dt.tz_convert(tz)

    t_state = state.get(ticker, {
        "in_position": False,
        "buy_date": None,
        "buy_price": None,
    })

    in_pos = t_state["in_position"]
    signal_now = bool(last["Signal"])

    # ===== CHƯA CÓ VỊ THẾ → XÉT MUA =====
    if not in_pos:
        if signal_now:
            t_state["in_position"] = True
            t_state["buy_date"]    = last_dt.isoformat()
            t_state["buy_price"]   = float(last["Close"])

            msg = (
                f"🟢 <b>MUA {ticker}</b>\n"
                f"Giá: {last['Close']:.2f}\n"
                f"Thời gian: {last_dt.strftime('%Y-%m-%d %H:%M')}\n"
                f"VolumeRatio: {last['VolumeRatio']:.2f} | "
                f"ROC10: {last['ROC10']:.2f}% | "
                f"MACD: {last['MACD_Hist']:.3f} | "
                f"ADX: {last['ADX14']:.1f}"
            )
            send_telegram(msg)
            print(f"  [{ticker}] BUY @ {last['Close']:.2f}")

    # ===== ĐANG CÓ VỊ THẾ → XÉT BÁN =====
    else:
        buy_dt = pd.to_datetime(t_state["buy_date"])
        if buy_dt.tz is None:
            buy_dt = buy_dt.tz_localize(tz)
        hold_days = (last_dt - buy_dt).days

        if (not signal_now) and (hold_days >= MIN_HOLD_DAYS):
            buy_price = t_state["buy_price"]
            ret = (last["Close"] / buy_price - 1) * 100
            ret_net = ret - FEE_PER_ROUND

            t_state["in_position"] = False
            t_state["buy_date"]    = None
            t_state["buy_price"]   = None

            msg = (
                f"🔴 <b>BÁN {ticker}</b>\n"
                f"Giá bán: {last['Close']:.2f} | Giá mua: {buy_price:.2f}\n"
                f"Return: {ret:+.2f}% (net {ret_net:+.2f}%)\n"
                f"Hold: {hold_days} phiên\n"
                f"Thời gian: {last_dt.strftime('%Y-%m-%d %H:%M')}"
            )
            send_telegram(msg)
            print(f"  [{ticker}] SELL @ {last['Close']:.2f} | ret {ret:+.2f}%")
        else:
            print(f"  [{ticker}] HOLD | {hold_days}p | sig={signal_now}")

    t_state["last_update"] = last_dt.isoformat()
    state[ticker] = t_state
    return state

# ===== MAIN =====
def main():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    print(f"===== ST5 CORE-TCH — {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")

    if now.weekday() >= 5:
        print("Cuối tuần — bỏ qua")
        return

    state = load_state()

    # ===== QUÉT 34 MÃ =====
    n_buy = 0
    n_sell = 0
    for i, ticker in enumerate(CORE_TCH, 1):
        old_pos = state.get(ticker, {}).get("in_position", False)
        state = process_ticker(ticker, state, tz)
        new_pos = state.get(ticker, {}).get("in_position", False)
        if not old_pos and new_pos: n_buy += 1
        if old_pos and not new_pos: n_sell += 1
        if i < len(CORE_TCH):
            time.sleep(DELAY_BETWEEN_TICKERS)

    save_state(state)
    print(f"\n===== DONE — BUY: {n_buy}, SELL: {n_sell}, Total: {len(CORE_TCH)} =====")

if __name__ == "__main__":
    main()
