import os
import json
import time
import requests
import pandas as pd

from config import (
    CORE26,
    MORNING_START,
    MORNING_END,
    AFTERNOON_START,
    AFTERNOON_END,
    TIMEZONE,
)

from data import get_intraday_data
from indicators import add_v14_indicators, v14_signal


STATE_FILE = "data/live_state.json"


def now_vietnam():
    return pd.Timestamp.now(tz=TIMEZONE)


def in_trading_session(now):
    if now.weekday() >= 5:
        return False

    t = now.strftime("%H:%M")

    return (
        MORNING_START <= t <= MORNING_END
        or
        AFTERNOON_START <= t <= AFTERNOON_END
    )


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            state = json.load(f)

        return state if isinstance(state, dict) else {}

    except Exception as e:
        print("⚠️ State lỗi:", e)
        return {}


def save_state(state):
    os.makedirs("data", exist_ok=True)

    temp_file = STATE_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_file,
        STATE_FILE
    )


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("❌ THIẾU TELEGRAM SECRETS")
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
            },
            timeout=15,
        )

        if response.ok:
            print("📨 Telegram: OK")
            return True

        print(
            "❌ Telegram lỗi:",
            response.status_code,
            response.text
        )

    except Exception as e:
        print(
            "❌ Telegram exception:",
            type(e).__name__,
            e
        )

    return False


def build_signal_message(
    ticker,
    action,
    row,
    now,
):
    price = float(row["Close"])
    vr = float(row["VolumeRatio"])
    roc = float(row["ROC10"])
    macd = float(row["MACD_Hist"])
    adx = float(row["ADX14"])

    return (
        f"🚨 ST5 {action}\n\n"
        f"Mã: {ticker}\n"
        f"Giá: {price:.2f}\n"
        f"Thời gian: "
        f"{now.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        f"Volume Ratio: {vr:.2f} "
        f"{'✅' if vr > 1.5 else '❌'}\n"
        f"ROC10: {roc:.2f}% "
        f"{'✅' if roc > 4.0 else '❌'}\n"
        f"MACD Hist: {macd:.4f} "
        f"{'✅' if macd > 0 else '❌'}\n"
        f"ADX14: {adx:.2f} "
        f"{'✅' if adx > 30 else '❌'}\n\n"
        f"ST5 V1.4: 4/4 HỘI TỤ"
    )


def process_ticker(
    ticker,
    state,
    now
):
    print(f"\n========== {ticker} ==========")

    try:
        df = get_intraday_data(
            ticker,
            days=5
        )

        if df.empty:
            print("❌ Không có dữ liệu")
            return False

        df = add_v14_indicators(df)

        df["Signal"] = v14_signal(df)

        df = df.dropna(
            subset=[
                "VolumeRatio",
                "ROC10",
                "MACD_Hist",
                "ADX14",
            ]
        )

        if df.empty:
            print("⏳ Chưa đủ dữ liệu")
            return False

        row = df.iloc[-1]

        signal = bool(row["Signal"])
        old_position = bool(
            state.get(ticker, False)
        )

        print(
            f"Price={row['Close']:.2f} | "
            f"VR={row['VolumeRatio']:.2f} | "
            f"ROC={row['ROC10']:.2f} | "
            f"MACD={row['MACD_Hist']:.4f} | "
            f"ADX={row['ADX14']:.2f}"
        )

        print(
            f"Signal={signal} | "
            f"State={old_position}"
        )

        if signal and not old_position:

            print("🟢 BUY SIGNAL")

            message = build_signal_message(
                ticker,
                "BUY",
                row,
                now
            )

            if send_telegram(message):
                state[ticker] = True
                save_state(state)

            return True

        if not signal and old_position:

            print("🔴 SELL SIGNAL")

            message = build_signal_message(
                ticker,
                "SELL",
                row,
                now
            )

            if send_telegram(message):
                state[ticker] = False
                save_state(state)

            return True

        print("— Không có tín hiệu mới")
        return False

    except Exception as e:

        print(
            f"❌ {ticker}: "
            f"{type(e).__name__}: {e}"
        )

        return False


def main():

    print("=" * 70)
    print("ST5 LIVE — V1.4 — INTRADAY 5M")
    print("=" * 70)

    now = now_vietnam()

    print(
        "Vietnam:",
        now.strftime("%Y-%m-%d %H:%M:%S")
    )

    if not in_trading_session(now):

        print("⏸ Ngoài giờ giao dịch")
        return

    print("🟢 ĐANG TRONG PHIÊN")

    state = load_state()

    print(
        f"CORE26: {len(CORE26)} mã"
    )

    signal_count = 0

    for index, ticker in enumerate(CORE26):

        changed = process_ticker(
            ticker,
            state,
            now
        )

        if changed:
            signal_count += 1

        # Giảm nguy cơ KBS rate-limit
        if index < len(CORE26) - 1:
            time.sleep(4)

    save_state(state)

    print()
    print(
        f"📊 Signal changes: "
        f"{signal_count}"
    )

    print("=" * 70)
    print("ST5 LIVE HOÀN TẤT")
    print("=" * 70)


if __name__ == "__main__":
    main()
