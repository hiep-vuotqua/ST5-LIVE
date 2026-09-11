# Scr/main_core_mbb.py
import os
import json
import time
import requests
import pandas as pd

from config_core_mbb import (
    CORE_MBB,
    VOLUME_RATIO_MIN,
    ROC10_MIN,
    MACD_HIST_MIN,
    ADX14_MIN,
    MIN_HOLD_DAYS,
    MORNING_START,
    MORNING_END,
    AFTERNOON_START,
    AFTERNOON_END,
    TIMEZONE,
)

from data_core_mbb import get_intraday_data
from indicators import add_v14_indicators, v14_signal


STATE_FILE = "data/live_state_core_mbb.json"


def now_vietnam():
    return pd.Timestamp.now(tz=TIMEZONE)


def in_trading_session(now):
    if now.weekday() >= 5:
        return False
    t = now.strftime("%H:%M")
    return (
        MORNING_START <= t <= MORNING_END
        or AFTERNOON_START <= t <= AFTERNOON_END
    )


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except Exception as e:
        print("⚠️ State lỗi:", e)
        return {}


def save_state(state):
    os.makedirs("data", exist_ok=True)
    temp_file = STATE_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, STATE_FILE)


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
            json={"chat_id": chat_id, "text": message},
            timeout=15,
        )
        if response.ok:
            print("📨 Telegram: OK")
            return True
        print("❌ Telegram lỗi:", response.status_code, response.text)
    except Exception as e:
        print("❌ Telegram exception:", type(e).__name__, e)
    return False


def build_signal_message(ticker, action, row, now, hold_info=""):
    price = float(row["Close"])
    vr = float(row["VolumeRatio"])
    roc = float(row["ROC10"])
    macd = float(row["MACD_Hist"])
    adx = float(row["ADX14"])
    return (
        f"🚨 ST5 CORE-MBB {action}\n\n"
        f"Mã: {ticker}\n"
        f"Giá adjusted: {price:.2f}\n"
        f"Thời gian: {now.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        f"Volume Ratio: {vr:.2f} {'✅' if vr > VOLUME_RATIO_MIN else '❌'}\n"
        f"ROC10: {roc:.2f}% {'✅' if roc > ROC10_MIN else '❌'}\n"
        f"MACD Hist: {macd:.4f} {'✅' if macd > MACD_HIST_MIN else '❌'}\n"
        f"ADX14: {adx:.2f} {'✅' if adx > ADX14_MIN else '❌'}\n\n"
        f"ST5 V1.4-MBB: 4/4 HỘI TỤ\n"
        f"\n⚠️ Giá đã điều chỉnh chia tách/cổ tức.\n"
        f"→ Kiểm tra giá sàn trước khi đặt lệnh."
        f"{hold_info}"
    )


def normalize_old_state(state):
    changed = False
    for ticker, value in list(state.items()):
        if isinstance(value, bool):
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
    position = bool(value.get("position", False))
    entry_date = value.get("entry_date")
    entry_time = value.get("entry_time")
    return position, entry_date, entry_time


def count_trading_days_since(df, entry_date):
    """
    Đếm số ngày giao dịch đã qua kể từ entry_date,
    dựa trên các ngày xuất hiện trong dữ liệu daily.
    """
    if not entry_date:
        return 0
    try:
        entry_date = pd.Timestamp(entry_date).date()
    except Exception:
        return 0

    dates = (
        pd.to_datetime(df["Date"], errors="coerce")
        .dt.date
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    dates = sorted(dates)
    future_dates = [d for d in dates if d > entry_date]
    return len(future_dates)


def can_sell_min_hold(df, entry_date, now):
    """
    CORE-MBB: chỉ được SELL khi đã đủ MIN_HOLD_DAYS ngày giao dịch.
    """
    if not entry_date:
        return False, "Không có ngày BUY"

    trading_days_passed = count_trading_days_since(df, entry_date)

    if trading_days_passed < MIN_HOLD_DAYS:
        remaining = MIN_HOLD_DAYS - trading_days_passed
        return (
            False,
            f"Chưa đủ min hold — còn {remaining} ngày giao dịch",
        )

    return True, f"ĐÃ ĐỦ {MIN_HOLD_DAYS} NGÀY GIAO DỊCH"


def process_ticker(ticker, state, now):
    print(f"\n========== {ticker} ==========")
    try:
        df = get_intraday_data(ticker, days=60)
        if df.empty:
            print("❌ Không có dữ liệu")
            return False

        df = add_v14_indicators(df)
        df["Signal"] = v14_signal(
            df,
            volume_ratio_min=VOLUME_RATIO_MIN,
            roc10_min=ROC10_MIN,
            macd_hist_min=MACD_HIST_MIN,
            adx14_min=ADX14_MIN,
        )
        df = df.dropna(
            subset=["VolumeRatio", "ROC10", "MACD_Hist", "ADX14"]
        )
        if df.empty:
            print("⏳ Chưa đủ dữ liệu")
            return False

        row = df.iloc[-1]
        signal = bool(row["Signal"])

        old_position, entry_date, entry_time = get_position_info(
            state, ticker
        )

        print(
            f"Price={row['Close']:.2f} | "
            f"VR={row['VolumeRatio']:.2f} | "
            f"ROC={row['ROC10']:.2f} | "
            f"MACD={row['MACD_Hist']:.4f} | "
            f"ADX={row['ADX14']:.2f}"
        )
        print(f"Signal={signal} | Position={old_position}")

        # BUY
        if signal and not old_position:
            print("🟢 BUY SIGNAL")
            message = build_signal_message(ticker, "BUY", row, now)
            if send_telegram(message):
                state[ticker] = {
                    "position": True,
                    "entry_date": now.strftime("%Y-%m-%d"),
                    "entry_time": now.strftime("%H:%M:%S"),
                }
                save_state(state)
                print(f"💾 BUY STATE SAVED: {ticker}")
            return True

        # SELL
        if old_position and not signal:
            can_sell, reason = can_sell_min_hold(df, entry_date, now)
            print(f"Min hold: {can_sell} | {reason}")
            if not can_sell:
                print("⏳ Tín hiệu mất nhưng CHƯA ĐỦ MIN HOLD -> GIỮ")
                return False

            print("🔴 SELL SIGNAL — ĐỦ MIN HOLD")
            message = build_signal_message(
                ticker, "SELL", row, now,
                hold_info=(
                    f"\n\n⏱ Min hold {MIN_HOLD_DAYS} ngày: ✅\n"
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
                print(f"💾 SELL STATE SAVED: {ticker}")
            return True

        if old_position:
            print("🟡 ĐANG GIỮ — chưa có SELL hợp lệ")
        else:
            print("— Không có tín hiệu mới")
        return False

    except Exception as e:
        print(f"❌ {ticker}: {type(e).__name__}: {e}")
        return False


def main():
    print("=" * 70)
    print("ST5 CORE-MBB LIVE — V1.4-MBB — MIN HOLD 10 NGÀY")
    print("=" * 70)

    now = now_vietnam()
    print("Vietnam:", now.strftime("%Y-%m-%d %H:%M:%S"))

    state = load_state()
    if normalize_old_state(state):
        save_state(state)
        print("💾 Đã reset state cũ")

    print(f"CORE-MBB: {len(CORE_MBB)} mã")

    signal_count = 0
    for index, ticker in enumerate(CORE_MBB):
        changed = process_ticker(ticker, state, now)
        if changed:
            signal_count += 1
        if index < len(CORE_MBB) - 1:
            time.sleep(3)

    save_state(state)
    print()
    print(f"📊 Signal changes: {signal_count}")
    print("=" * 70)
    print("ST5 CORE-MBB LIVE HOÀN TẤT")
    print("=" * 70)


if __name__ == "__main__":
    main() 
