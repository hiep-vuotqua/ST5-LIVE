import os
import json
import time
from datetime import datetime

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

from data_core_dgw import (
    get_intraday_data,
    get_vnindex,
)


# ============================================================
# TIME
# ============================================================

VN_TZ = pytz.timezone(TIMEZONE)


def now_vn():
    return datetime.now(VN_TZ)


def is_trading_session(dt):
    t = dt.strftime("%H:%M")

    return (
        "09:00" <= t <= "11:30"
        or
        "13:00" <= t <= "15:30"
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
            return json.load(f)

    except Exception as e:

        print(
            f"State load error: {e}"
        )

        return {}


def save_state(state):

    folder = os.path.dirname(
        STATE_FILE
    )

    if folder:
        os.makedirs(
            folder,
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

        print(
            "Telegram secrets chưa được cấu hình."
        )

        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    try:

        r = requests.post(
            url,
            json=payload,
            timeout=20
        )

        if r.ok:

            print("Telegram: OK")

            return True

        print(
            "Telegram ERROR:",
            r.status_code,
            r.text
        )

        return False

    except Exception as e:

        print(
            "Telegram EXCEPTION:",
            e
        )

        return False


# ============================================================
# INDICATORS
# ============================================================

def add_indicators(df):

    df = df.copy()

    df["Date"] = pd.to_datetime(
        df["Date"]
    )

    df = (
        df
        .sort_values("Date")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Volume Ratio
    # --------------------------------------------------------

    vol_ma20 = (
        df["Volume"]
        .rolling(20)
        .mean()
    )

    df["VolumeRatio"] = (
        df["Volume"] / vol_ma20
    )

    # --------------------------------------------------------
    # ROC10
    # --------------------------------------------------------

    df["ROC10"] = (
        df["Close"]
        .pct_change(10)
        * 100
    )

    # --------------------------------------------------------
    # MACD Histogram
    # --------------------------------------------------------

    ema12 = (
        df["Close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        df["Close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    macd = ema12 - ema26

    macd_signal = (
        macd
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["MACD_HIST"] = (
        macd - macd_signal
    )

    # --------------------------------------------------------
    # ADX14
    # --------------------------------------------------------

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    prev_close = close.shift(1)

    tr1 = high - low

    tr2 = (
        high - prev_close
    ).abs()

    tr3 = (
        low - prev_close
    ).abs()

    tr = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    up_move = high.diff()

    down_move = -low.diff()

    plus_dm = np.where(
        (up_move > down_move)
        & (up_move > 0),
        up_move,
        0.0
    )

    minus_dm = np.where(
        (down_move > up_move)
        & (down_move > 0),
        down_move,
        0.0
    )

    tr_ewm = (
        pd.Series(tr, index=df.index)
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
    )

    plus_dm_ewm = (
        pd.Series(
            plus_dm,
            index=df.index
        )
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
    )

    minus_dm_ewm = (
        pd.Series(
            minus_dm,
            index=df.index
        )
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
    )

    plus_di = (
        100
        * plus_dm_ewm
        / tr_ewm
    )

    minus_di = (
        100
        * minus_dm_ewm
        / tr_ewm
    )

    di_sum = (
        plus_di + minus_di
    )

    dx = (
        100
        * (plus_di - minus_di).abs()
        / di_sum.replace(0, np.nan)
    )

    adx = (
        dx
        .ewm(
            alpha=1 / 14,
            adjust=False
        )
        .mean()
    )

    df["ADX14"] = adx

    return df


# ============================================================
# VNI FILTER
# ============================================================

def add_vni_filter(df, vni):

    df = df.copy()
    vni = vni.copy()

    df["Date"] = pd.to_datetime(
        df["Date"]
    )

    vni["Date"] = pd.to_datetime(
        vni["Date"]
    )

    vni = (
        vni
        .sort_values("Date")
        .reset_index(drop=True)
    )

    vni["MA20"] = (
        vni["Close"]
        .rolling(VNI_MA_PERIOD)
        .mean()
    )

    vni["VNI_FILTER"] = (
        vni["Close"]
        > vni["MA20"]
    )

    vni_merge = vni[
        [
            "Date",
            "Close",
            "MA20",
            "VNI_FILTER"
        ]
    ].copy()

    vni_merge = vni_merge.rename(
        columns={
            "Close": "VNI_Close",
            "MA20": "VNI_MA20",
        }
    )

    df = pd.merge_asof(
        df.sort_values("Date"),
        vni_merge.sort_values("Date"),
        on="Date",
        direction="backward"
    )

    return df


# ============================================================
# SIGNAL
# ============================================================

def core_dgw_signal(row):

    required = [
        "VolumeRatio",
        "ROC10",
        "MACD_HIST",
        "ADX14",
        "VNI_FILTER",
    ]

    for col in required:

        if pd.isna(row[col]):
            return False

    return (
        row["VolumeRatio"]
        >= VOLUME_RATIO_MIN
        and
        row["ROC10"]
        >= ROC10_MIN
        and
        row["MACD_HIST"]
        >= MACD_HIST_MIN
        and
        row["ADX14"]
        >= ADX14_MIN
        and
        bool(row["VNI_FILTER"])
    )


# ============================================================
# PROCESS TICKER
# ============================================================

def process_ticker(
    ticker,
    state,
    vni
):

    print()
    print("=" * 70)
    print(
        f"{ticker} — CORE-DGW"
    )
    print("=" * 70)

    try:

        df = get_intraday_data(
            ticker,
            days=400
        )

        if df is None or df.empty:

            print(
                f"{ticker}: Không có dữ liệu."
            )

            return

        print(
            f"{ticker}: "
            f"{len(df)} rows"
        )

        df = add_indicators(df)

        df = add_vni_filter(
            df,
            vni
        )

        df = df.dropna(
            subset=[
                "VolumeRatio",
                "ROC10",
                "MACD_HIST",
                "ADX14",
                "VNI_FILTER",
            ]
        ).reset_index(
            drop=True
        )

        if df.empty:

            print(
                f"{ticker}: "
                f"Không đủ dữ liệu indicator."
            )

            return

        df["SIGNAL"] = df.apply(
            core_dgw_signal,
            axis=1
        )

        last = df.iloc[-1]

        signal_date = pd.Timestamp(
            last["Date"]
        ).strftime("%Y-%m-%d")

        signal = bool(
            last["SIGNAL"]
        )

        print(
            f"Date        : {signal_date}"
        )

        print(
            f"Close       : "
            f"{last['Close']:.2f}"
        )

        print(
            f"VolumeRatio : "
            f"{last['VolumeRatio']:.3f}"
        )

        print(
            f"ROC10       : "
            f"{last['ROC10']:.3f}"
        )

        print(
            f"MACD_HIST   : "
            f"{last['MACD_HIST']:.5f}"
        )

        print(
            f"ADX14       : "
            f"{last['ADX14']:.3f}"
        )

        print(
            f"VNI_FILTER  : "
            f"{bool(last['VNI_FILTER'])}"
        )

        print(
            f"SIGNAL      : "
            f"{signal}"
        )

        ticker_state = state.get(
            ticker,
            {
                "in_position": False,
                "buy_date": None,
                "buy_price": None,
                "last_processed_date": None,
            }
        )

        # ----------------------------------------------------
        # DUPLICATE
        # ----------------------------------------------------

        if (
            ticker_state.get(
                "last_processed_date"
            )
            == signal_date
        ):

            print(
                f"{ticker}: "
                f"Đã xử lý {signal_date}."
            )

            state[ticker] = ticker_state

            return

        # ----------------------------------------------------
        # NO POSITION
        # ----------------------------------------------------

        if not ticker_state.get(
            "in_position",
            False
        ):

            if signal:

                ticker_state[
                    "in_position"
                ] = True

                ticker_state[
                    "buy_date"
                ] = signal_date

                ticker_state[
                    "buy_price"
                ] = None

                message = (
                    f"🟢 {TELEGRAM_TITLE}\n"
                    f"BUY SIGNAL: {ticker}\n\n"
                    f"Signal date: {signal_date}\n"
                    f"Action: BUY NEXT OPEN\n"
                    f"Close: {last['Close']:.2f}\n"
                    f"VolR: {last['VolumeRatio']:.2f}\n"
                    f"ROC10: {last['ROC10']:.2f}\n"
                    f"MACD Hist: "
                    f"{last['MACD_HIST']:.4f}\n"
                    f"ADX14: {last['ADX14']:.2f}\n"
                    f"VNI > MA20: YES"
                )

                send_telegram(
                    message
                )

                print(
                    f"{ticker}: "
                    f"BUY SIGNAL"
                )

            else:

                print(
                    f"{ticker}: "
                    f"Không có BUY."
                )

        # ----------------------------------------------------
        # IN POSITION
        # ----------------------------------------------------

        else:

            buy_date = ticker_state.get(
                "buy_date"
            )

            if buy_date:

                buy_dt = pd.Timestamp(
                    buy_date
                )

                hold_sessions = int(
                    (
                        df["Date"]
                        > buy_dt
                    ).sum()
                )

            else:

                hold_sessions = 0

            print(
                f"{ticker}: "
                f"IN POSITION | "
                f"Hold={hold_sessions}"
            )

            if (
                not signal
                and
                hold_sessions
                >= MIN_HOLD_DAYS
            ):

                message = (
                    f"🔴 {TELEGRAM_TITLE}\n"
                    f"SELL SIGNAL: {ticker}\n\n"
                    f"Signal date: {signal_date}\n"
                    f"Hold sessions: "
                    f"{hold_sessions}\n"
                    f"Close: {last['Close']:.2f}\n"
                    f"VolR: "
                    f"{last['VolumeRatio']:.2f}\n"
                    f"ROC10: "
                    f"{last['ROC10']:.2f}\n"
                    f"MACD Hist: "
                    f"{last['MACD_HIST']:.4f}\n"
                    f"ADX14: "
                    f"{last['ADX14']:.2f}\n"
                    f"VNI > MA20: "
                    f"{'YES' if bool(last['VNI_FILTER']) else 'NO'}"
                )

                send_telegram(
                    message
                )

                ticker_state = {
                    "in_position": False,
                    "buy_date": None,
                    "buy_price": None,
                    "last_processed_date":
                        signal_date,
                }

                print(
                    f"{ticker}: "
                    f"SELL SIGNAL"
                )

            else:

                print(
                    f"{ticker}: "
                    f"Giữ vị thế."
                )

        ticker_state[
            "last_processed_date"
        ] = signal_date

        state[ticker] = ticker_state

    except Exception as e:

        print(
            f"{ticker}: ERROR -> "
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    now = now_vn()

    print(
        f"===== {TELEGRAM_TITLE} — "
        f"{now.strftime('%Y-%m-%d %H:%M:%S %z')} ====="
    )

    # TEST MODE:
    # ngoài giờ vẫn chạy để kiểm tra dữ liệu.
    if not is_trading_session(now):

        print(
            f"Ngoài giờ giao dịch "
            f"({now.strftime('%H:%M')}) "
            f"— TEST MODE, vẫn chạy"
        )

    state = load_state()

    print(
        f"CORE-DGW tickers: "
        f"{len(CORE_DGW)}"
    )

    print(
        "Danh sách:",
        ", ".join(CORE_DGW)
    )

    # --------------------------------------------------------
    # VNINDEX
    # --------------------------------------------------------

    print()
    print(
        "Loading VNINDEX..."
    )

    vni = get_vnindex()

    if vni is None or vni.empty:

        print(
            "VNINDEX: "
            "KHÔNG TẢI ĐƯỢC."
        )

        return

    print(
        f"VNINDEX rows: "
        f"{len(vni)}"
    )

    # --------------------------------------------------------
    # STOCKS
    # --------------------------------------------------------

    for i, ticker in enumerate(
        CORE_DGW,
        start=1
    ):

        print()
        print(
            f"[{i}/{len(CORE_DGW)}] "
            f"Processing {ticker}"
        )

        process_ticker(
            ticker,
            state,
            vni
        )

        save_state(
            state
        )

        if i < len(CORE_DGW):

            print(
                f"Sleep "
                f"{DELAY_BETWEEN_TICKERS}s..."
            )

            time.sleep(
                DELAY_BETWEEN_TICKERS
            )

    # --------------------------------------------------------
    # FINAL SAVE
    # --------------------------------------------------------

    save_state(
        state
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    in_position = []

    for ticker in CORE_DGW:

        ticker_state = state.get(
            ticker,
            {}
        )

        if ticker_state.get(
            "in_position",
            False
        ):

            in_position.append(
                ticker
            )

    print()
    print("=" * 70)
    print(
        "CORE-DGW FINISHED"
    )
    print("=" * 70)

    print(
        f"Processed: "
        f"{len(CORE_DGW)}"
    )

    print(
        f"State file: "
        f"{STATE_FILE}"
    )

    print(
        f"In position: "
        f"{len(in_position)}"
    )

    if in_position:

        print(
            "Positions:",
            ", ".join(
                in_position
            )
        )

    print("=" * 70)


if __name__ == "__main__":
    main() 
