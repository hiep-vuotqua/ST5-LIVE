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

# ============================================================
# T+2.5 STRATEGY HOLDING RULE
#
# BUY:
#   Signal 4/4 xuất hiện -> BUY
#
# SELL:
#   Chỉ được SELL khi:
#       - đã qua 2 ngày giao dịch kể từ ngày BUY
#       - và đang ở phiên chiều từ 13:00
#
# Ví dụ:
#   BUY:  Thứ Hai 10:00
#   HOLD: Thứ Ba
#   HOLD: Thứ Tư buổi sáng
#   SELL: Thứ Tư từ 13:00 nếu tín hiệu SELL
# ============================================================


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
                "text": message
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
    hold_info=""
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
        f"{hold_info}"
    )


def normalize_old_state(state):
    """
    Hỗ trợ state cũ dạng:
        {
            "VCI": true
        }

    Nhưng state mới sẽ là:
        {
            "VCI": {
                "position": true,
                "entry_date": "...",
                "entry_time": "..."
            }
        }

    State cũ không có ngày mua -> không thể xác định T+2.5.
    Vì vậy reset state cũ về FLAT để tránh bán/mua sai.
    """

    changed = False

    for ticker, value in list(state.items()):

        if isinstance(value, bool):

            print(
                f"⚠️ {ticker}: state cũ không có "
                f"ngày mua -> reset FLAT"
            )

            state[ticker] = {
                "position": False,
                "entry_date": None,
                "entry_time": None,
            }

            changed = True

    return changed


def get_position_info(state, ticker):

    value = state.get(ticker)

    if not isinstance(value, dict):
        return False, None, None

    position = bool(
        value.get("position", False)
    )

    entry_date = value.get(
        "entry_date"
    )

    entry_time = value.get(
        "entry_time"
    )

    return (
        position,
        entry_date,
        entry_time
    )


def can_sell_t25(
    df,
    entry_date,
    now
):
    """
    Xác định đã đủ T+2.5 theo NGÀY GIAO DỊCH thực tế
    xuất hiện trong dữ liệu intraday.

    Ví dụ:
        BUY Monday
        trading date +1 = Tuesday
        trading date +2 = Wednesday

    SELL chỉ được phép:
        Wednesday >= 13:00
    """

    if not entry_date:
        return False, "Không có ngày BUY"

    try:
        entry_date = pd.Timestamp(
            entry_date
        ).date()

    except Exception:
        return False, "entry_date không hợp lệ"

    # Lấy các ngày giao dịch có trong data
    dates = (
        pd.to_datetime(
            df["Date"],
            errors="coerce"
        )
        .dt.date
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    dates = sorted(dates)

    future_trading_dates = [
        d for d in dates
        if d > entry_date
    ]

    if len(future_trading_dates) < 2:

        return (
            False,
            "Chưa đủ 2 ngày giao dịch"
        )

    second_trading_day = (
        future_trading_dates[1]
    )

    current_date = now.date()

    # Chưa tới ngày giao dịch thứ 2
    if current_date < second_trading_day:

        return (
            False,
            f"Chờ T+2.5 — ngày bán sớm nhất "
            f"{second_trading_day.strftime('%d/%m/%Y')} "
            f"13:00"
        )

    # Nếu đang đúng ngày T+2
    # phải chờ phiên chiều
    if current_date == second_trading_day:

        current_time = now.strftime(
            "%H:%M"
        )

        if current_time < AFTERNOON_START:

            return (
                False,
                f"Đã T+2 nhưng chưa tới "
                f"{AFTERNOON_START}"
            )

    # Nếu đã qua T+2.5
    return True, "ĐÃ ĐỦ T+2.5"


def process_ticker(
    ticker,
    state,
    now
):

    print(
        f"\n========== {ticker} =========="
    )

    try:

        # ----------------------------------------------------
        # DATA
        # ----------------------------------------------------

        df = get_intraday_data(
            ticker,
            days=5
        )

        if df.empty:

            print("❌ Không có dữ liệu")

            return False

        # ----------------------------------------------------
        # INDICATORS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # CURRENT BAR
        # ----------------------------------------------------

        row = df.iloc[-1]

        signal = bool(
            row["Signal"]
        )

        (
            old_position,
            entry_date,
            entry_time
        ) = get_position_info(
            state,
            ticker
        )

        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------

        print(
            f"Price={row['Close']:.2f} | "
            f"VR={row['VolumeRatio']:.2f} | "
            f"ROC={row['ROC10']:.2f} | "
            f"MACD={row['MACD_Hist']:.4f} | "
            f"ADX={row['ADX14']:.2f}"
        )

        print(
            f"Signal={signal} | "
            f"Position={old_position}"
        )

        if entry_date:

            print(
                f"Entry={entry_date} "
                f"{entry_time or ''}"
            )

        # ====================================================
        # BUY
        # ====================================================

        if signal and not old_position:

            print("🟢 BUY SIGNAL")

            message = build_signal_message(
                ticker,
                "BUY",
                row,
                now
            )

            if send_telegram(message):

                state[ticker] = {
                    "position": True,
                    "entry_date": now.strftime(
                        "%Y-%m-%d"
                    ),
                    "entry_time": now.strftime(
                        "%H:%M:%S"
                    ),
                }

                save_state(state)

                print(
                    f"💾 BUY STATE SAVED: "
                    f"{ticker}"
                )

            return True

        # ====================================================
        # SELL
        # ====================================================

        if old_position and not signal:

            can_sell, reason = can_sell_t25(
                df,
                entry_date,
                now
            )

            print(
                f"T+2.5: {can_sell} | "
                f"{reason}"
            )

            # ------------------------------------------------
            # CHƯA ĐỦ T+2.5
            # ------------------------------------------------

            if not can_sell:

                print(
                    "⏳ Tín hiệu đã mất nhưng "
                    "CHƯA ĐỦ T+2.5 -> TIẾP TỤC GIỮ"
                )

                return False

            # ------------------------------------------------
            # ĐỦ T+2.5 -> SELL
            # ------------------------------------------------

            print(
                "🔴 SELL SIGNAL — ĐỦ T+2.5"
            )

            message = build_signal_message(
                ticker,
                "SELL",
                row,
                now,
                hold_info=(
                    f"\n\n⏱ T+2.5: ✅\n"
                    f"Ngày BUY: {entry_date}\n"
                    f"Giờ BUY: {entry_time}"
                )
            )

            if send_telegram(message):

                state[ticker] = {
                    "position": False,
                    "entry_date": None,
                    "entry_time": None,
                }

                save_state(state)

                print(
                    f"💾 SELL STATE SAVED: "
                    f"{ticker}"
                )

            return True

        # ====================================================
        # HOLD
        # ====================================================

        if old_position:

            print(
                "🟡 ĐANG GIỮ — "
                "chưa có SELL hợp lệ"
            )

        else:

            print(
                "— Không có tín hiệu mới"
            )

        return False

    except Exception as e:

        print(
            f"❌ {ticker}: "
            f"{type(e).__name__}: {e}"
        )

        return False


def main():

    print("=" * 70)
    print(
        "ST5 LIVE — V1.4 — "
        "INTRADAY 5M — T+2.5 HOLD"
    )
    print("=" * 70)

    now = now_vietnam()

    print(
        "Vietnam:",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    if not in_trading_session(now):

        print(
            "⏸ Ngoài giờ giao dịch"
        )

        return

    print(
        "🟢 ĐANG TRONG PHIÊN"
    )

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    state = load_state()

    # Reset state cũ dạng boolean
    if normalize_old_state(state):

        save_state(state)

        print(
            "💾 Đã reset state cũ"
        )

    print(
        f"CORE26: {len(CORE26)} mã"
    )

    signal_count = 0

    # --------------------------------------------------------
    # CORE26
    # --------------------------------------------------------

    for index, ticker in enumerate(
        CORE26
    ):

        changed = process_ticker(
            ticker,
            state,
            now
        )

        if changed:

            signal_count += 1

        # Giảm KBS rate-limit
        if index < len(CORE26) - 1:

            time.sleep(4)

    # --------------------------------------------------------
    # FINAL STATE
    # --------------------------------------------------------

    save_state(state)

    print()

    print(
        f"📊 Signal changes: "
        f"{signal_count}"
    )

    print("=" * 70)
    print(
        "ST5 LIVE T+2.5 HOÀN TẤT"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
