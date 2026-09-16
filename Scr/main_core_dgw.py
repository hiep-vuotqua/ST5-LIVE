# ============================================================
# ST5-LIVE — CORE-DGW
# Engine LIVE — Daily 1D
# FINAL 20
# ============================================================

import os
import json
import time
from datetime import datetime

import pytz
import pandas as pd
import numpy as np
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
    FEE_PER_ROUND,
    DELAY_BETWEEN_TICKERS,
    MORNING_START,
    MORNING_END,
    AFTERNOON_START,
    AFTERNOON_END,
)

from data_core_dgw import (
    get_intraday_data,
    get_vnindex,
)


TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    ""
)

TELEGRAM_CHAT_ID = os.environ.get(
    "TELEGRAM_CHAT_ID",
    ""
)


# ============================================================
# STATE
# ============================================================

def load_state():

    abs_path = os.path.abspath(
        STATE_FILE
    )

    print(
        f"  [load_state] Reading from: "
        f"{abs_path}"
    )

    if os.path.exists(STATE_FILE):

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    print(
        "  [load_state] File không tồn tại, "
        "trả về rỗng"
    )

    return {}


def save_state(state):

    os.makedirs(
        os.path.dirname(STATE_FILE),
        exist_ok=True
    )

    abs_path = os.path.abspath(
        STATE_FILE
    )

    print(
        f"  [save_state] Writing to: "
        f"{abs_path}"
    )

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False,
            default=str
        )


# ============================================================
# INDICATORS
# ============================================================

def add_indicators(df):

    df = df.copy()

    # Volume Ratio
    vol_ma = (
        df["Volume"]
        .rolling(20)
        .mean()
    )

    df["VolumeRatio"] = (
        df["Volume"] / vol_ma
    )

    # ROC10
    df["ROC10"] = (
        df["Close"]
        .pct_change(10)
        * 100
    )

    # MACD Histogram
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

    signal = (
        macd
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["MACD_Hist"] = (
        macd - signal
    )

    # ADX14
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1
    ).max(axis=1)

    up = high.diff()
    down = -low.diff()

    plus_dm = pd.Series(
        np.where(
            (up > down) &
            (up > 0),
            up,
            0
        ),
        index=df.index
    )

    minus_dm = pd.Series(
        np.where(
            (down > up) &
            (down > 0),
            down,
            0
        ),
        index=df.index
    )

    atr = tr.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    plus_di = (
        100
        * plus_dm.ewm(
            alpha=1 / 14,
            adjust=False
        ).mean()
        / atr
    )

    minus_di = (
        100
        * minus_dm.ewm(
            alpha=1 / 14,
            adjust=False
        ).mean()
        / atr
    )

    dx = (
        100
        * (plus_di - minus_di).abs()
        / (
            plus_di + minus_di
        ).replace(
            0,
            np.nan
        )
    )

    df["ADX14"] = (
        dx.ewm(
            alpha=1 / 14,
            adjust=False
        ).mean()
    )

    return df


# ============================================================
# VNINDEX FILTER
# ============================================================

def add_vni_filter(df, vni):

    df = df.copy()
    vni = vni.copy()

    vni["VNI_MA20"] = (
        vni["Close"]
        .rolling(VNI_MA_PERIOD)
        .mean()
    )

    vni["VNI_FILTER"] = (
        vni["Close"]
        > vni["VNI_MA20"]
    )

    vni_filter = vni[
        [
            "Date",
            "VNI_FILTER"
        ]
    ].copy()

    df = pd.merge_asof(
        df.sort_values("Date"),
        vni_filter.sort_values("Date"),
        on="Date",
        direction="backward"
    )

    return df


# ============================================================
# SIGNAL
# ============================================================

def core_dgw_signal(df):

    return (
        (df["VolumeRatio"] >= VOLUME_RATIO_MIN)
        &
        (df["ROC10"] >= ROC10_MIN)
        &
        (df["MACD_Hist"] >= MACD_HIST_MIN)
        &
        (df["ADX14"] >= ADX14_MIN)
        &
        (df["VNI_FILTER"].fillna(False))
    )


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(msg):

    if (
        not TELEGRAM_BOT_TOKEN
        or not TELEGRAM_CHAT_ID
    ):
        print(
            "[WARN] Telegram chưa cấu hình"
        )
        return

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}"
        "/sendMessage"
    )

    try:

        requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text":
                    f"[{TELEGRAM_TITLE}] "
                    f"{msg}",
                "parse_mode": "HTML",
            },
            timeout=10
        )

    except Exception as e:

        print(
            f"[ERROR] Telegram: {e}"
        )


# ============================================================
# XỬ LÝ 1 MÃ
# ============================================================

def process_ticker(
    ticker,
    state,
    tz
):

    try:

        df = get_intraday_data(
            ticker,
            days=400
        )

    except Exception as e:

        print(
            f"  [{ticker}] ERROR data: {e}"
        )

        return state

    if (
        df is None
        or len(df) < 30
    ):

        print(
            f"  [{ticker}] SKIP — "
            f"không đủ dữ liệu"
        )

        return state

    try:

        vni = get_vnindex()

    except Exception as e:

        print(
            f"  [{ticker}] ERROR VNI: {e}"
        )

        return state

    if (
        vni is None
        or len(vni) < 30
    ):

        print(
            f"  [{ticker}] SKIP — "
            f"VNINDEX không đủ dữ liệu"
        )

        return state

    df = add_indicators(df)

    df = add_vni_filter(
        df,
        vni
    )

    df["Signal"] = (
        core_dgw_signal(df)
    )

    last = df.iloc[-1]

    last_date = pd.to_datetime(
        last["Date"]
    ).date()

    t_state = state.get(
        ticker,
        {
            "in_position": False,
            "buy_date": None,
            "buy_price": None,
            "last_date": None,
        }
    )

    # ========================================================
    # CHỐNG TRÙNG NGÀY
    # ========================================================

    if (
        t_state.get("last_date")
        == str(last_date)
    ):

        print(
            f"  [{ticker}] SKIP — "
            f"đã xử lý ngày {last_date}"
        )

        return state

    signal_now = bool(
        last["Signal"]
    )

    print(
        f"  [{ticker}] {last_date} | "
        f"C={last['Close']:.2f} | "
        f"VolR={last['VolumeRatio']:.2f} | "
        f"ROC10={last['ROC10']:.2f} | "
        f"MACD={last['MACD_Hist']:.3f} | "
        f"ADX={last['ADX14']:.1f} | "
        f"VNI={bool(last['VNI_FILTER'])} | "
        f"sig={signal_now}"
    )

    # ========================================================
    # CHƯA CÓ VỊ THẾ → BUY
    # ========================================================

    if not t_state["in_position"]:

        if signal_now:

            # Tín hiệu xuất hiện ở cuối phiên.
            # Thực thi theo nguyên tắc backtest:
            # NEXT DAY OPEN.
            t_state["in_position"] = True
            t_state["buy_date"] = str(
                last_date
            )
            t_state["buy_price"] = None
            t_state["last_date"] = str(
                last_date
            )

            msg = (
                f"🟢 <b>TÍN HIỆU MUA {ticker}</b>\n"
                f"Giá đóng cửa adjusted: "
                f"{last['Close']:.2f}\n"
                f"Ngày tín hiệu: {last_date}\n"
                f"→ Đặt lệnh tại OPEN phiên kế tiếp.\n"
                f"\n"
                f"VolR: "
                f"{last['VolumeRatio']:.2f}\n"
                f"ROC10: "
                f"{last['ROC10']:.2f}%\n"
                f"MACD: "
                f"{last['MACD_Hist']:.3f}\n"
                f"ADX: "
                f"{last['ADX14']:.1f}\n"
                f"VNI > MA20: "
                f"{bool(last['VNI_FILTER'])}\n"
                f"\n"
                f"⚠️ Giá adjusted.\n"
                f"→ Kiểm tra giá sàn trước khi "
                f"đặt lệnh."
            )

            send_telegram(msg)

            print(
                f"  [{ticker}] "
                f">>> BUY SIGNAL "
                f"(next OPEN)"
            )

    # ========================================================
    # ĐANG CÓ VỊ THẾ → SELL
    # ========================================================

    else:

        buy_dt = pd.to_datetime(
            t_state["buy_date"]
        ).date()

        # Đếm số phiên kể từ ngày tín hiệu mua
        hold_sessions = len(
            df[
                (
                    df["Date"].dt.date
                    > buy_dt
                )
                &
                (
                    df["Date"].dt.date
                    <= last_date
                )
            ]
        )

        if (
            not signal_now
            and hold_sessions >= MIN_HOLD_DAYS
        ):

            buy_price = (
                t_state.get(
                    "buy_price"
                )
            )

            ret_text = "N/A"

            if (
                buy_price is not None
                and buy_price > 0
            ):

                ret = (
                    last["Close"]
                    / buy_price
                    - 1
                ) * 100

                ret_net = (
                    ret
                    - FEE_PER_ROUND
                )

                ret_text = (
                    f"{ret:+.2f}% "
                    f"(net "
                    f"{ret_net:+.2f}%)"
                )

            t_state[
                "in_position"
            ] = False

            t_state[
                "buy_date"
            ] = None

            t_state[
                "buy_price"
            ] = None

            t_state[
                "last_date"
            ] = str(last_date)

            msg = (
                f"🔴 <b>TÍN HIỆU BÁN "
                f"{ticker}</b>\n"
                f"Giá đóng cửa adjusted: "
                f"{last['Close']:.2f}\n"
                f"Ngày: {last_date}\n"
                f"Hold: "
                f"{hold_sessions} phiên\n"
                f"Return: {ret_text}\n"
                f"\n"
                f"VolR: "
                f"{last['VolumeRatio']:.2f}\n"
                f"ROC10: "
                f"{last['ROC10']:.2f}%\n"
                f"MACD: "
                f"{last['MACD_Hist']:.3f}\n"
                f"ADX: "
                f"{last['ADX14']:.1f}\n"
                f"\n"
                f"⚠️ Giá adjusted.\n"
                f"→ Kiểm tra giá sàn trước khi "
                f"đặt lệnh."
            )

            send_telegram(msg)

            print(
                f"  [{ticker}] "
                f">>> SELL SIGNAL"
            )

        else:

            t_state[
                "last_date"
            ] = str(last_date)

            print(
                f"  [{ticker}] HOLD | "
                f"{hold_sessions} phiên | "
                f"sig={signal_now}"
            )

    state[ticker] = t_state

    return state


# ============================================================
# MAIN
# ============================================================

def main():

    tz = pytz.timezone(
        TIMEZONE
    )

    now = datetime.now(tz)

    print(
        f"===== ST5 CORE-DGW — "
        f"{now.strftime('%Y-%m-%d %H:%M:%S %Z')} ====="
    )

    if now.weekday() >= 5:

        print(
            "Cuối tuần — bỏ qua"
        )

        return

    # ========================================================
    # CHECK GIỜ
    # ========================================================

    t = now.strftime("%H:%M")

    in_session = (
        (
            MORNING_START
            <= t
            <= MORNING_END
        )
        or
        (
            AFTERNOON_START
            <= t
            <= AFTERNOON_END
        )
    )

    if not in_session:

        print(
            f"Ngoài giờ giao dịch "
            f"({t}) — bỏ qua"
        )

        return

    # ========================================================
    # STATE
    # ========================================================

    state = load_state()

    n_buy = 0
    n_sell = 0

    # ========================================================
    # SCAN 20 MÃ
    # ========================================================

    for i, ticker in enumerate(
        CORE_DGW,
        1
    ):

        old_pos = state.get(
            ticker,
            {}
        ).get(
            "in_position",
            False
        )

        state = process_ticker(
            ticker,
            state,
            tz
        )

        new_pos = state.get(
            ticker,
            {}
        ).get(
            "in_position",
            False
        )

        if (
            not old_pos
            and new_pos
        ):
            n_buy += 1

        if (
            old_pos
            and not new_pos
        ):
            n_sell += 1

        if i < len(CORE_DGW):

            time.sleep(
                DELAY_BETWEEN_TICKERS
            )

    save_state(state)

    print(
        f"\n===== DONE — "
        f"BUY: {n_buy}, "
        f"SELL: {n_sell}, "
        f"Total: {len(CORE_DGW)} ====="
    )


if __name__ == "__main__":
    main()
