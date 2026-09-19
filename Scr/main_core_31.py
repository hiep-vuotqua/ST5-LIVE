"""CORE-31 engine — variant B."""

import os
import json
import time
from datetime import datetime
import pytz
import pandas as pd
import requests

from config_core_31 import (
    CORE_31, VOLUME_RATIO_MIN, ROC10_MIN, MACD_HIST_MIN, ADX14_MIN,
    USE_MA200, USE_MA50, MIN_HOLD_DAYS, TIMEZONE, STATE_FILE,
    TELEGRAM_TITLE, FEE_PER_ROUND, DELAY_BETWEEN_TICKERS
)
from data_core_31 import get_intraday_data
from indicators import add_v14_indicators

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


def load_state():
    abs_path = os.path.abspath(STATE_FILE)
    print(f"  [load_state] Reading: {abs_path}")
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"  [load_state] Không tồn tại, trả về rỗng")
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


def process_ticker(ticker, state, tz):
    try:
        df = get_intraday_data(ticker, days=120)
    except Exception as e:
        print(f"  [{ticker}] ERROR data: {e}")
        return state

    if df is None or len(df) < 250:
        print(f"  [{ticker}] SKIP — {len(df)} nến (cần 250)")
        return state

    df["MA50"]  = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    df = add_v14_indicators(df)
    df = df.dropna().reset_index(drop=True)

    if len(df) == 0:
        print(f"  [{ticker}] SKIP — dropna hết data")
        return state

    df["Signal"] = core_signal(df)

    last = df.iloc[-1]
    last_date = pd.to_datetime(last["Date"]).date()

    t_state = state.get(ticker, {
        "in_position": False, "buy_date": None,
        "buy_price": None, "last_date": None,
    })

    if t_state.get("last_date") == str(last_date):
        print(f"  [{ticker}] SKIP — đã xử lý ngày {last_date}")
        return state

    in_pos = t_state["in_position"]
    signal_now = bool(last["Signal"])

    print(f"  [{ticker}] {last_date} | C={last['Close']:.2f} | "
          f"VolR={last['VolumeRatio']:.2f} | ROC10={last['ROC10']:.2f} | "
          f"MACD={last['MACD_Hist']:.3f} | ADX={last['ADX14']:.1f} | sig={signal_now}")

    if not in_pos:
        if signal_now:
            t_state["in_position"] = True
            t_state["buy_date"]    = str(last_date)
            t_state["buy_price"]   = float(last["Close"])
            t_state["last_date"]   = str(last_date)

            msg = (
                f"🟢 <b>MUA {ticker}</b>\n"
                f"Giá adjusted: {last['Close']:.2f}\n"
                f"Ngày: {last_date}\n"
                f"VolR: {last['VolumeRatio']:.2f} | "
                f"ROC10: {last['ROC10']:.2f}% | "
                f"MACD: {last['MACD_Hist']:.3f} | "
                f"ADX: {last['ADX14']:.1f}\n"
                f"\n⚠️ Giá đã điều chỉnh chia tách/cổ tức.\n"
                f"→ Kiểm tra giá sàn trước khi đặt lệnh."
            )
            send_telegram(msg)
            print(f"  [{ticker}] >>> BUY @ {last['Close']:.2f}")
    else:
        buy_dt = pd.to_datetime(t_state["buy_date"]).date()
        hold_days = (last_date - buy_dt).days

        if (not signal_now) and (hold_days >= MIN_HOLD_DAYS):
            buy_price = t_state["buy_price"]
            ret = (last["Close"] / buy_price - 1) * 100
            ret_net = ret - FEE_PER_ROUND

            t_state["in_position"] = False
            t_state["buy_date"]    = None
            t_state["buy_price"]   = None
            t_state["last_date"]   = str(last_date)

            msg = (
                f"🔴 <b>BÁN {ticker}</b>\n"
                f"Giá bán (adjusted): {last['Close']:.2f}\n"
                f"Giá mua (adjusted): {buy_price:.2f}\n"
                f"Return: {ret:+.2f}% (net {ret_net:+.2f}%)\n"
                f"Hold: {hold_days} ngày\n"
                f"Ngày: {last_date}\n"
                f"\n⚠️ Giá đã điều chỉnh chia tách/cổ tức.\n"
                f"→ Kiểm tra giá sàn trước khi đặt lệnh."
            )
            send_telegram(msg)
            print(f"  [{ticker}] >>> SELL @ {last['Close']:.2f} | ret {ret:+.2f}%")
        else:
            t_state["last_date"] = str(last_date)
            print(f"  [{ticker}] HOLD | {hold_days} ngày | sig={signal_now}")

    state[ticker] = t_state
    return state


def main():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    print(f"===== ST5 CORE-31 — {now.strftime('%Y-%m-%d %H:%M:%S %Z')} =====")

    if now.weekday() >= 5:
        print("Cuối tuần — bỏ qua")
        return

    state = load_state()

    n_buy = n_sell = 0
    for i, ticker in enumerate(CORE_31, 1):
        old_pos = state.get(ticker, {}).get("in_position", False)
        state = process_ticker(ticker, state, tz)
        new_pos = state.get(ticker, {}).get("in_position", False)
        if not old_pos and new_pos: n_buy += 1
        if old_pos and not new_pos: n_sell += 1
        if i < len(CORE_31):
            time.sleep(DELAY_BETWEEN_TICKERS)

    save_state(state)
    print(f"\n===== DONE — BUY: {n_buy}, SELL: {n_sell}, Total: {len(CORE_31)} =====")


if __name__ == "__main__":
    main()
