import os
import json
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytz
import requests

from config_core_dgw import (
    CORE_DGW,
    VOLUME_RATIO_MIN,
    ROC10_MIN,
    MACD_HIST_MIN,
    ADX14_MIN,
    MIN_HOLD_DAYS,
    VNI_MA_PERIOD,
    TIMEZONE,
    STATE_FILE,
    TELEGRAM_TITLE,
    DELAY_BETWEEN_TICKERS,
)
from data_core_dgw import get_intraday_data, get_vnindex


# ============================================================
# TIME
# ============================================================

VN_TZ = pytz.timezone(TIMEZONE)


def now_vn():
    return datetime.now(VN_TZ)


def is_trading_session(dt):
    t = dt.strftime("%H:%M")

    morning = "09:00" <= t <= "11:30"
    afternoon = "13:00" <= t <= "15:30"

    return morning or afternoon


# ============================================================
# STATE
# ============================================================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    folder = os.path.dirname(STATE_FILE)

    if folder:
        os.makedirs(folder, exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram secrets chưa được cấu hình.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    try:
        r = requests.post(url, json=payload, timeout=20)

        if r.ok:
            print("Telegram: OK")
            return True

        print("Telegram ERROR:", r.status_code, r.text)
        return False

    except Exception as e:
        print("Telegram EXCEPTION:", e)
        return False


# ============================================================
# INDICATORS
# ============================================================

def add_indicators(df):
    df = df.copy()

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    # -------------------------
    # Volume Ratio
    # -------------------------
    vol_ma20 = df["Volume"].rolling(20).mean()
    df["VolumeRatio"] = df["Volume"] / vol_ma20

    # -------------------------
    # ROC10
    # -------------------------
    df["ROC10"] = df["Close"].pct_change(10) * 100

    # -------------------------
    # MACD Histogram
    # -------------------------
    ema12 = df["Close"].ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = df["Close"].ewm(
        span=26,
        adjust=False
    ).mean()

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9,
        adjust=False
    ).mean()

    df["MACD_HIST"] = macd - signal

    # -------------------------
    # ADX14
    # -------------------------
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where(
        (up_move > down_move) & (up_move > 0),
        up_move,
        0.0
    )

    minus_dm = np.where(
        (down_move > up_move) & (down_move > 0),
        down_move,
        0.0
    )

    tr_ewm = pd.Series(tr).ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    plus_dm_ewm = pd.Series(plus_dm).ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    minus_dm_ewm = pd.Series(minus_dm).ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    plus_di = 100 * plus_dm_ewm / tr_ewm
    minus_di = 100 * minus_dm_ewm / tr_ewm

    dx = (
        100
        * (plus_di - minus_di).abs()
        / (plus_di + minus_di)
    )

    adx = dx.ewm(
        alpha=1 / 14,
        adjust=False
