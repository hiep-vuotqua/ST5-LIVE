import os
import json
import time
import requests
import pandas as pd

from config import (
    MORNING_START,
    MORNING_END,
    AFTERNOON_START,
    AFTERNOON_END,
    TIMEZONE,
)

from data import get_intraday_data
from indicators import add_v14_indicators


# ============================================================
# ST5 LIVE — V1.8 SURVIVAL
# ============================================================
#
# 33 MÃ:
#   WINNER  : 16
#   STRONG  : 10
#   WATCH   : 7
#
# ENTRY:
#   ADX14 > 40
#   AND
#   MACD_HIST_SLOPE > 0
#
# EXIT:
#   MACD_Hist <= 0
#   OR ROC10 <= 2
#   OR ADX14 <= 30
#
# KHÔNG:
#   Volume filter
#   ROC entry filter
#   TP / SL
#   Max Hold
#
# State riêng hoàn toàn với V1.4
# ============================================================


STATE_FILE = "data/v18_live_state.json"


V18_SYMBOLS = [

    # ========================================================
    # WINNER — 16
    # ========================================================
    "THD", "VIB", "PVD", "SSI", "SHS", "KBC",
    "VCI", "HPG", "VIX", "SIP", "PLX", "ABB",
    "API", "VPB", "CII", "AAS",

    # ========================================================
    # STRONG — 10
    # ========================================================
    "CEO", "APG", "ACV", "KDC", "DXG",
    "VCG", "NKG", "EVF", "DGC", "ADS",

    # ========================================================
    # WATCH — 7
    # ========================================================
    "GMD", "NAF", "POW", "MBB", "SHB", "HDB", "DPM",
]


WINNER = {
    "THD", "VIB", "PVD", "SSI", "SHS", "KBC",
    "VCI", "HPG", "VIX", "SIP", "PLX", "ABB",
    "API", "VPB", "CII", "AAS",
}

STRONG = {
    "CEO", "APG", "ACV", "KDC", "DXG",
    "VCG", "NKG", "EVF", "DGC", "ADS",
}

WATCH = {
    "GMD", "NAF", "POW", "MBB", "SHB", "HDB", "DPM",
}


# ============================================================
# TIME
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

            state = json.load(f)

        return (
            state
            if isinstance(state, dict)
            else {}
        )

    except Exception as e:

        print("⚠️ V1.8 State lỗi:", e)

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


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:

        print("❌ THIẾU TELEGRAM SECRETS")

        return False

    url = (
        "https://api.telegram.org/"
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

            print("📨 Telegram V1.8: OK")

            return True

        print(
            "❌ Telegram V1.8 lỗi:",
            response.status_code,
            response.text
        )

    except Exception as e:

        print(
            "❌ Telegram V1.8 exception:",
            type(e).__name__,
            e
        )

    return False


# ============================================================
# CLASSIFICATION
# ============================================================

def ticker_class(ticker):

    if ticker in WINNER:
        return "WINNER"

    if ticker in STRONG:
        return "STRONG"

    if ticker in WATCH:
        return "WATCH"

    return "UNKNOWN"


# ============================================================
# SIGNAL MESSAGE
# ============================================================

def build_signal_message(
    ticker,
    action,
    row,
    now
):

    price = float(row["Close"])
    roc = float(row["ROC10"])
    macd = float(row["MACD_Hist"])
    slope = float(row["MACD_HIST_SLOPE"])
    adx = float(row["ADX14"])

    classification = ticker_class(ticker)

    if action == "BUY":

        return (
            f"🚨 ST5 V1.8 BUY\n\n"
            f"Mã: {ticker}\n"
            f"Nhóm: {classification}\n"
            f"Giá: {price:.2f}\n"
            f"Thời gian: "
            f"{now.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"ADX14: {adx:.2f} ✅ > 40\n"
            f"MACD Hist: {macd:.4f}\n"
            f"MACD Hist Slope: {slope:.6f} ✅ > 0\n"
            f"ROC10: {roc:.2f}%\n\n"
            f"V1.8: 2/2 ĐIỀU KIỆN ENTRY"
        )

    return (
        f"🔴 ST5 V1.8 SELL\n\n"
        f"Mã: {ticker}\n"
        f"Nhóm: {classification}\n"
        f"Giá: {price:.2f}\n"
        f"Thời gian: "
        f"{now.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        f"ADX14: {adx:.2f}\n"
        f"MACD Hist: {macd:.4f}\n"
        f"MACD Hist Slope: {slope:.6f}\n"
        f"ROC10: {roc:.2f}%\n\n"
        f"V1.8 EXIT:\n"
        f"MACD Hist <= 0 "
        f"OR ROC10 <= 2 "
        f"OR ADX14 <= 30"
    )


# ============================================================
# V1.8 SIGNAL ENGINE
# ============================================================

def entry_condition(row):

    return (
        float(row["ADX14"]) > 40.0
        and
        float(row["MACD_HIST_SLOPE"]) > 0.0
    )


def exit_condition(row):

    return (
        float(row["MACD_Hist"]) <= 0.0
        or
        float(row["ROC10"]) <= 2.0
        or
        float(row["ADX14"]) <= 30.0
    )


# ============================================================
# PROCESS TICKER
# ============================================================

def process_ticker(
    ticker,
    state,
    now
):

    print()
    print(
        f"========== V1.8 {ticker} "
        f"[{ticker_class(ticker)}] =========="
    )

    try:

        # ----------------------------------------------------
        # LOAD 5M
        # ----------------------------------------------------

        df = get_intraday_data(
            ticker,
            days=5
        )

        if df is None or df.empty:

            print("❌ Không có dữ liệu")

            return False

        # ----------------------------------------------------
        # INDICATORS
        # ----------------------------------------------------

        df = add_v14_indicators(df)

        # V1.8:
        # MACD Histogram slope
        df["MACD_HIST_SLOPE"] = (
            df["MACD_Hist"].diff()
        )

        df = df.dropna(
            subset=[
                "ROC10",
                "MACD_Hist",
                "MACD_HIST_SLOPE",
                "ADX14",
            ]
        )

        if df.empty:

            print("⏳ Chưa đủ dữ liệu indicator")

            return False

        # ----------------------------------------------------
        # LATEST BAR
        # ----------------------------------------------------

        row = df.iloc[-1]

        entry = entry_condition(row)
        exit_signal = exit_condition(row)

        old_position = bool(
            state.get(ticker, False)
        )

        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------

        print(
            f"Price={float(row['Close']):.2f} | "
            f"ADX={float(row['ADX14']):.2f} | "
            f"MACD={float(row['MACD_Hist']):.4f} | "
            f"Slope={float(row['MACD_HIST_SLOPE']):.6f} | "
            f"ROC={float(row['ROC10']):.2f}"
        )

        print(
            f"ENTRY={entry} | "
            f"EXIT={exit_signal} | "
            f"STATE={old_position}"
        )

        # ----------------------------------------------------
        # SELL — ƯU TIÊN KHI ĐANG CÓ VỊ THẾ
        # ----------------------------------------------------

        if old_position and exit_signal:

            print("🔴 V1.8 SELL SIGNAL")

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

            return False

        # ----------------------------------------------------
        # BUY
        # ----------------------------------------------------

        if not old_position and entry:

            print("🟢 V1.8 BUY SIGNAL")

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

            return False

        # ----------------------------------------------------
        # NOTHING
        # ----------------------------------------------------

        print("— Không có tín hiệu mới")

        return False

    except Exception as e:

        print(
            f"❌ V1.8 {ticker}: "
            f"{type(e).__name__}: {e}"
        )

        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 75)
    print("ST5 LIVE — V1.8 SURVIVAL — INTRADAY 5M")
    print("=" * 75)

    now = now_vietnam()

    print(
        "Vietnam:",
        now.strftime("%Y-%m-%d %H:%M:%S")
    )

    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    if not in_trading_session(now):

        print("⏸ Ngoài giờ giao dịch")

        return

    print("🟢 ĐANG TRONG PHIÊN")

    # --------------------------------------------------------
    # SYMBOL CHECK
    # --------------------------------------------------------

    if len(V18_SYMBOLS) != 33:

        print(
            "❌ LỖI: V1.8 không đủ 33 mã"
        )

        return

    if len(set(V18_SYMBOLS)) != 33:

        print(
            "❌ LỖI: V1.8 có mã trùng"
        )

        return

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    state = load_state()

    print(
        f"V1.8 SYMBOLS: "
        f"{len(V18_SYMBOLS)} mã"
    )

    signal_count = 0

    # --------------------------------------------------------
    # PROCESS
    # --------------------------------------------------------

    for index, ticker in enumerate(
        V18_SYMBOLS
    ):

        changed = process_ticker(
            ticker,
            state,
            now
        )

        if changed:

            signal_count += 1

        # KBS rate-limit protection
        if index < len(V18_SYMBOLS) - 1:

            time.sleep(4)

    # --------------------------------------------------------
    # FINAL STATE
    # --------------------------------------------------------

    save_state(state)

    print()
    print(
        f"📊 V1.8 Signal changes: "
        f"{signal_count}"
    )

    print("=" * 75)
    print("ST5 V1.8 LIVE HOÀN TẤT")
    print("=" * 75)


if __name__ == "__main__":

    main()
