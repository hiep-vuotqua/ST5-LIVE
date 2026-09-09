import os
import json
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

    morning = MORNING_START <= t <= MORNING_END
    afternoon = AFTERNOON_START <= t <= AFTERNOON_END

    return morning or afternoon


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    os.makedirs("data", exist_ok=True)

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


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("❌ THIẾU TELEGRAM SECRETS")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

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
        print("❌ Telegram exception:", e)

    return False


def send_test():
    return send_telegram(
        "🟢 ST5 LIVE TEST\n\n"
        "GitHub Actions → Telegram hoạt động bình thường."
    )


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
        f"Thời gian: {now.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        f"Volume Ratio: {vr:.2f} {'✅' if vr > 1.5 else '❌'}\n"
        f"ROC10: {roc:.2f}% {'✅' if roc > 4.0 else '❌'}\n"
        f"MACD Hist: {macd:.4f} {'✅' if macd > 0 else '❌'}\n"
        f"ADX14: {adx:.2f} {'✅' if adx > 30 else '❌'}\n\n"
        f"ST5: 4/4 HỘI TỤ"
    )


def process_ticker(ticker, state, now):
    print(f"\n[{ticker}]")

    try:
        df = get_intraday_data(
            ticker,
            days=5
        )

        if df.empty:
            print("❌ Không có dữ liệu")
            return

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
            print("⏳ Chưa đủ dữ liệu indicator")
            return

        row = df.iloc[-1]

        signal = bool(row["Signal"])
        old_position = bool(state.get(ticker, False))

        print(
            f"Price={row['Close']:.2f} | "
            f"VR={row['VolumeRatio']:.2f} | "
            f"ROC={row['ROC10']:.2f} | "
            f"MACD={row['MACD_Hist']:.4f} | "
            f"ADX={row['ADX14']:.2f} | "
            f"Signal={signal}"
        )

        # =========================
        # BUY
        # =========================

        if signal and not old_position:

            print("🟢 BUY")

            message = build_signal_message(
                ticker,
                "BUY",
                row,
                now
            )

            if send_telegram(message):
                state[ticker] = True
                save_state(state)

        # =========================
        # SELL
        # =========================

        elif not signal and old_position:

            print("🔴 SELL")

            message = build_signal_message(
                ticker,
                "SELL",
                row,
                now
            )

            if send_telegram(message):
                state[ticker] = False
                save_state(state)

        else:
            print("— Không có tín hiệu mới")

    except Exception as e:
        print(
            f"❌ {ticker}: "
            f"{type(e).__name__}: {e}"
        )


def main():

    print("=" * 70)
    print("ST5 LIVE — INTRADAY 5M")
    print("=" * 70)

    now = now_vietnam()

    print(
        "Vietnam:",
        now.strftime("%Y-%m-%d %H:%M:%S")
    )

    # =========================
    # TELEGRAM TEST
    # =========================

    if os.getenv("TELEGRAM_TEST") == "1":
        print("📨 TELEGRAM TEST")
        send_test()
        return

    # =========================
    # SESSION CHECK
    # =========================

    if not in_trading_session(now):

        print("⏸ Ngoài giờ giao dịch")

        return

    print("🟢 ĐANG TRONG PHIÊN")

    state = load_state()

    print(
        f"CORE26: {len(CORE26)} mã"
    )

    for ticker in CORE26:

        process_ticker(
            ticker,
            state,
            now
        )

    print()
    print("=" * 70)
    print("ST5 LIVE HOÀN TẤT")
    print("=" * 70)


if __name__ == "__main__":
    main()
