# Scr/data_core_msra.py
# Data fetcher CORE-MSRA — daily 1D
# Nguồn: vnstock (KBS → VCI)

import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from config_core_msra import DATA_START

try:
    from vnstock.api.quote import Quote
    VNSTOCK_OK = True
except Exception as e:
    VNSTOCK_OK = False
    print(f"  [CẢNH BÁO] Không import được vnstock: {e}")


def load_stock(ticker):
    """Load daily KBS → VCI. Set attrs['source']."""
    if not VNSTOCK_OK:
        return None

    end_date = datetime.now().strftime("%Y-%m-%d")

    for source in ["KBS", "VCI"]:
        try:
            q = Quote(symbol=ticker, source=source)
            df = q.history(start=DATA_START, end=end_date, interval="1D")

            if df is None or len(df) < 300:
                print(f"  [{ticker}][{source}] chỉ {len(df) if df is not None else 0} nến")
                continue

            df.columns = [str(c).strip().lower() for c in df.columns]
            rename = {
                "time": "Date", "date": "Date",
                "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume",
            }
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

            need = ["Date", "Open", "High", "Low", "Close", "Volume"]
            if not all(c in df.columns for c in need):
                continue

            df = df[need].copy()
            df["Date"] = pd.to_datetime(df["Date"])
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            df = (df.dropna()
                    .drop_duplicates(subset=["Date"])
                    .sort_values("Date")
                    .reset_index(drop=True))
            df = df[df["Volume"] > 0].reset_index(drop=True)

            if len(df) < 300:
                continue

            df.attrs["source"] = source
            time.sleep(0.5)
            return df

        except Exception as e:
            print(f"  [{ticker}][{source}] Fail: {str(e)[:100]}")
            continue

    return None


def add_indicators(df):
    """Wilder's-ADX — chuẩn quốc tế."""
    df = df.copy()
    df["VolMA20"] = df["Volume"].rolling(20).mean()
    df["VolumeRatio"] = df["Volume"] / df["VolMA20"]
    df["ROC10"] = df["Close"].pct_change(10) * 100

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = macd - signal

    period = 14
    high, low, close = df["High"], df["Low"], df["Close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df["ADX14"] = dx.ewm(alpha=1/period, adjust=False).mean()

    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    return df


def add_signal(df, adx_min=22):
    """Luật V3 — dùng config."""
    from config_core_msra import (
        VOL_RATIO_MIN, ROC10_MIN, MACD_HIST_MIN,
    )
    df = df.copy()
    df["Signal"] = (
        (df["VolumeRatio"] >= VOL_RATIO_MIN) &
        (df["ROC10"] >= ROC10_MIN) &
        (df["MACD_HIST_MIN"] if False else df["MACD_Hist"] >= MACD_HIST_MIN) &
        (df["ADX14"] >= adx_min) &
        (df["Close"] > df["MA200"]) &
        (df["Close"] > df["MA50"])
    )
    return df
