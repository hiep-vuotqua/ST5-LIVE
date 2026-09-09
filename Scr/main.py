import os
import json
import time
import requests
import pandas as pd

from config import (
    CORE26,
    INITIAL_CAPITAL,
    POSITION_PCT,
    MORNING_START,
    MORNING_END,
    AFTERNOON_START,
    AFTERNOON_END,
    TIMEZONE,
    CHECK_INTERVAL_MINUTES,
)

from data import get_intraday_data
from indicators import add_v14_indicators, v14_signal


STATE_FILE = "data/live_state.json"


# ============================================================
# TIME
# ============================================================

def now_vietnam():
    return pd.Timestamp.now(
        tz=TIMEZONE
    )


def in_trading_session(now):
    current = now.strftime("%H:%M")

    morning = (
        MORNING_START
        <= current
        <= MORNING_END
    )

    afternoon = (
        AFTERNOON_START
        <= current
        <= AFTERNOON_END
    )

    return morning or afternoon


# ============================================================
# STATE
# ============================================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return {}


def save_state(state):

    os.makedirs(
        os.path.dirname(STATE_FILE),
        exist_ok=True
    )

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN"
    )

    chat_id = os.getenv(
        "TELEGRAM_CHAT_ID"
    )

    if not token or not chat_id:
        print("❌ Thiếu Telegram Secrets")
        return False

    url = (
        f"https://api.telegram.org/bot"
        f"{token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        if response.ok:
            print("📨 Telegram: OK")
            return True

        print(
            "❌ Telegram lỗi:",
            response.text
        )

        return False

    except Exception as e:

        print(
            "❌ Telegram exception:",
            e
        )

        return False


# ============================================================
# SIGNAL MESSAGE
# ============================================================

def build_message(
    ticker,
    action,
    row,
    now
):

    vr = row["VolumeRatio"]
    roc = row["ROC10"]
    macd = row["MACD_Hist"]
    adx = row["ADX14"]
    price = row["Close"]

    message = (
        f"🚨 ST5 {action}\n\n"
        f"Mã: {ticker}\n"
        f"Giá: {price:.2f}\n"
        f"Thời gian: {now.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        f"Volume Ratio: {vr:.2f} {'✅' if vr > 1.5 else '❌'}\n"
        f"ROC10: {roc:.2f}% {'✅' if roc > 4 else '❌'}\n"
        f"MACD Hist: {macd:.4f} {'✅' if macd > 0 else '❌'}\n"
        f"ADX14: {adx:.2f} {'✅' if adx > 30 else '❌'}\n\n"
        f"ST5: 4/4 hội tụ"
    )

    return message


# ============================================================
# PROCESS ONE TICKER
# ============================================================

def process_ticker(
    ticker,
    state,
    now
):

    print(
        f"\n[{ticker}] Đang kiểm tra..."
    )

    try:

        df = get_intraday_data(
            ticker,
            days=5
        )

        if df.empty:
            print(
                f"[{ticker}] Không có dữ liệu"
            )
            return

        df = add_v14_indicators(df)

        df["Signal"] = v14_signal(df)

        row = df.iloc[-1]

        signal = bool(row["Signal"])

        previous_position = bool(
            state.get(
                ticker,
                False
            )
        )

        # ====================================================
        # BUY
        # ====================================================

        if signal and not previous_position:

            print(
                f"🟢 {ticker}: BUY"
            )

            message = build_message(
                ticker,
                "BUY",
                row,
                now
            )

            if send_telegram(message):

                state[ticker] = True
                save_state(state)

        # ====================================================
        # SELL
        # ====================================================

        elif not signal and previous_position:

            print(
                f"🔴 {ticker}: SELL"
            )

            message = build_message(
                ticker,
                "SELL",
                row,
                now
            )

            if send_telegram(message):

                state[ticker] = False
                save_state(state)

        else:

            print(
                f"[{ticker}] "
                f"Không có tín hiệu mới"
            )

    except Exception as e:

        print(
            f"❌ {ticker}: {type(e).__name__}: {e}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("ST5 LIVE — V1.4")
    print("=" * 70)

    now = now_vietnam()

    print(
        "Vietnam time:",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    if now.weekday() >= 5:

        print(
            "⛔ Cuối tuần — không giao dịch"
        )

        return

    if not in_trading_session(now):

        print(
            "⏸ Ngoài giờ giao dịch"
        )

        return

    print(
        "🟢 ĐANG TRONG PHIÊN"
    )

    state = load_state()

    for ticker in CORE26:

        process_ticker(
            ticker,
            state,
            now
        )

        time.sleep(2)

    print()
    print("=" * 70)
    print("ST5 LIVE HOÀN TẤT")
    print("=" * 70)


if __name__ == "__main__":
    main()
