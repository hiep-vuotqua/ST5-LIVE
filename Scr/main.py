import os
import json
import time
import requests
import pandas as pd
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from data import get_intraday_data
from indicators import add_v14_indicators


SYMBOLS = [
    "THD", "VIB", "PVD", "SSI", "SHS", "KBC", "VCI", "HPG",
    "VIX", "SIP", "PLX", "ABB", "API", "VPB", "CII", "AAS",
    "CEO", "APG", "ACV", "KDC", "DXG", "VCG", "NKG", "EVF",
    "DGC", "ADS",
    "GMD", "NAF", "POW", "MBB", "SHB", "HDB", "DPM"
]

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
STATE_FILE = "data/v18_live_state.json"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def now_vn():
    return datetime.now(TZ)


def in_trading_session():
    now = now_vn()

    if now.weekday() >= 5:
        return False

    t = now.time()

    morning = dtime(9, 15) <= t <= dtime(11, 30)
    afternoon = dtime(13, 0) <= t <= dtime(14, 30)

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
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    tmp = STATE_FILE + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    os.replace(tmp, STATE_FILE)


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()

    data = r.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data}")


def classify(symbol):
    winner = {
        "THD", "VIB", "PVD", "SSI", "SHS", "KBC", "VCI", "HPG",
        "VIX", "SIP", "PLX", "ABB", "API", "VPB", "CII", "AAS"
    }

    strong = {
        "CEO", "APG", "ACV", "KDC", "DXG",
        "VCG", "NKG", "EVF", "DGC", "ADS"
    }

    watch = {
        "GMD", "NAF", "POW", "MBB", "SHB", "HDB", "DPM"
    }

    if symbol in winner:
        return "WINNER"
    if symbol in strong:
        return "STRONG"
    if symbol in watch:
        return "WATCH"

    return "UNKNOWN"


def calculate_v18(df):
    df = df.copy()

    df["MACD_HIST_SLOPE"] = df["MACD_Hist"].diff()

    df["ENTRY"] = (
        (df["ADX14"] > 40) &
        (df["MACD_HIST_SLOPE"] > 0)
    )

    df["EXIT"] = (
        (df["MACD_Hist"] <= 0) |
        (df["ROC10"] <= 2) |
        (df["ADX14"] <= 30)
    )

    return df


def build_message(symbol, action, row):
    reason = ""

    if action == "BUY":
        reason = "ADX14 > 40 + MACD HIST SLOPE > 0"

    elif action == "SELL":
        reasons = []

        if row["MACD_Hist"] <= 0:
            reasons.append("MACD_Hist <= 0")

        if row["ROC10"] <= 2:
            reasons.append("ROC10 <= 2")

        if row["ADX14"] <= 30:
            reasons.append("ADX14 <= 30")

        reason = " OR ".join(reasons)

    return (
        f"🚨 VRE SURVIVAL V1.8 — {action}\n"
        f"Mã: {symbol}\n"
        f"Nhóm: {classify(symbol)}\n"
        f"Giá: {row['Close']:.2f}\n"
        f"ADX14: {row['ADX14']:.2f}\n"
        f"MACD Hist: {row['MACD_Hist']:.6f}\n"
        f"MACD Hist Slope: {row['MACD_HIST_SLOPE']:.6f}\n"
        f"ROC10: {row['ROC10']:.2f}%\n"
        f"Lý do: {reason}\n"
        f"Thời gian: {now_vn().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def process_symbol(symbol, state):
    try:
        df = get_intraday_data(symbol, days=5, retries=3)

        if df is None or df.empty:
            print(f"{symbol}: NO DATA")
            return

        df = add_v14_indicators(df)

        df["MACD_HIST_SLOPE"] = df["MACD_Hist"].diff()

        df = df.dropna(
            subset=[
                "Close",
                "ROC10",
                "MACD_Hist",
                "MACD_HIST_SLOPE",
                "ADX14"
            ]
        )

        if df.empty:
            print(f"{symbol}: NO VALID ROW")
            return

        row = df.iloc[-1]

        entry = bool(
            row["ADX14"] > 40 and
            row["MACD_HIST_SLOPE"] > 0
        )

        exit_signal = bool(
            row["MACD_Hist"] <= 0 or
            row["ROC10"] <= 2 or
            row["ADX14"] <= 30
        )

        old_position = bool(
            state.get(symbol, {}).get("position", False)
        )

        action = None

        if old_position and exit_signal:
            action = "SELL"

        elif not old_position and entry:
            action = "BUY"

        if action:
            message = build_message(symbol, action, row)

            send_telegram(message)

            state[symbol] = {
                "position": action == "BUY",
                "last_action": action,
                "last_bar": str(row["Date"]),
                "updated_at": now_vn().isoformat()
            }

            print(
                f"{symbol}: {action} | "
                f"Close={row['Close']:.2f} "
                f"ADX={row['ADX14']:.2f} "
                f"MACD={row['MACD_Hist']:.6f} "
                f"SLOPE={row['MACD_HIST_SLOPE']:.6f} "
                f"ROC={row['ROC10']:.2f}"
            )

        else:
            print(
                f"{symbol}: HOLD | "
                f"entry={entry} exit={exit_signal} "
                f"position={old_position}"
            )

    except Exception as e:
        print(f"{symbol}: ERROR: {e}")


def main():
    print("=" * 80)
    print("VRE SURVIVAL V1.8 LIVE")
    print("=" * 80)

    if not in_trading_session():
        print("Outside trading session.")
        return

    state = load_state()

    for symbol in SYMBOLS:
        process_symbol(symbol, state)
        save_state(state)
        time.sleep(4)

    save_state(state)

    print("=" * 80)
    print("V1.8 RUN COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
