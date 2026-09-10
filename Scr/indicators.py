import numpy as np
import pandas as pd

def volume_ratio(df, period=20):
    return (
        df["Volume"]
        / df["Volume"].rolling(period).mean()
    )


def roc10(df):
    return df["Close"].pct_change(10) * 100.0


def macd_histogram(df):
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

    return macd - signal


def adx14(df, period=14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

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

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr = tr.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    plus_di = (
        pd.Series(
            plus_dm,
            index=df.index
        )
        .ewm(
            alpha=1 / period,
            adjust=False
        )
        .mean()
        / atr
        * 100
    )

    minus_di = (
        pd.Series(
            minus_dm,
            index=df.index
        )
        .ewm(
            alpha=1 / period,
            adjust=False
        )
        .mean()
        / atr
        * 100
    )

    denominator = (
        plus_di + minus_di
    ).replace(0, np.nan)

    dx = (
        (plus_di - minus_di).abs()
        / denominator
        * 100
    )

    return dx.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()


def add_v14_indicators(df):
    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(z
            f"Thiếu cột dữ liệu: {missing}"
        )

    df = df.copy()

    df["VolumeRatio"] = volume_ratio(df)
    df["ROC10"] = roc10(df)
    df["MACD_Hist"] = macd_histogram(df)
    df["ADX14"] = adx14(df)

    return df


def v14_signal(
    df,
    volume_ratio_min=1.5,
    roc10_min=4.0,
    macd_hist_min=0.0,
    adx14_min=30.0,
):
    required = [
        "VolumeRatio",
        "ROC10",
        "MACD_Hist",
        "ADX14"
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Thiếu indicator: {missing}"
        )

    return (
        (df["VolumeRatio"] > volume_ratio_min)
        & (df["ROC10"] > roc10_min)
        & (df["MACD_Hist"] > macd_hist_min)
        & (df["ADX14"] > adx14_min)
    )
