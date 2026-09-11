# ============================================================
# CORE-MSRA DATA — Load KBS→VCI + indicators (giống backtest)
# ============================================================
import numpy as np
import pandas as pd
from datetime import datetime
from config_core_msra import DATA_START


def load_stock(ticker):
    """Load daily KBS→VCI fallback. Set attrs['source']."""
    from vnstock import Quote
    end_date = datetime.now().strftime("%Y-%m-%d")
    for source in ["KBS", "VCI"]:
        try:
            q = Quote(source=source, symbol=ticker)
            df = q.history(start=DATA_START, end=end_date, interval="1D")
            if df is None or len(df) < 300:
                continue
            df.columns = [str(c).strip().lower() for c in df.columns]
            rename = {"time": "Date", "date": "Date", "open": "Open",
                      "high": "High", "low": "Low", "close": "Close",
                      "volume": "Volume"}
            df = df.rename(columns={k: v for k, v in rename.items()
                                     if k in df.columns})
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
            return df
        except Exception:
            continue
    return None


def add_indicators(df):
    """Công thức giống backtest_adx (SMA-ADX)."""
    df = df.copy()
    df["VolMA20"] = df["Volume"].rolling(20).mean()
    df["VolumeRatio"] = df["Volume"] / df["VolMA20"]
    df["ROC10"] = df["Close"].pct_change(10) * 100

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = macd - signal

    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df["ADX14"] = dx.rolling(14).mean()

    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    return df


def add_signal(df, adx_min=30):
    """Luật A1i+50 — dấu >= giống backtest."""
    df = df.copy()
    df["Signal"] = (
        (df["VolumeRatio"] >= 1.5) &
        (df["ROC10"] >= 4.0) &
        (df["MACD_Hist"] >= 0.0) &
        (df["ADX14"] >= adx_min) &
        (df["Close"] > df["MA200"]) &
        (df["Close"] > df["MA50"])
    )
    return df 
