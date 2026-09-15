# ============================================================
# CORE-MSRA DATA — TCBS API (không rate limit) + indicators
# ============================================================
import os
import time
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from config_core_msra import DATA_START

# ============ CACHE ============
CACHE_DIR = "cache_data"
CACHE_TTL_HOURS = 4  # Cache 4 giờ


def _cache_path(ticker):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{ticker}.csv")


def _load_cache(ticker):
    path = _cache_path(ticker)
    if not os.path.exists(path):
        return None
    age_hours = (time.time() - os.path.getmtime(path)) / 3600
    if age_hours > CACHE_TTL_HOURS:
        return None
    try:
        df = pd.read_csv(path, parse_dates=["Date"])
        df.attrs["source"] = "cache"
        return df
    except Exception:
        return None


def _save_cache(ticker, df):
    try:
        df.to_csv(_cache_path(ticker), index=False)
    except Exception:
        pass


# ============ TCBS API ============
def _load_tcbs(ticker):
    """TCBS public API — không cần key, không rate limit."""
    url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
    start_ts = int(pd.Timestamp(DATA_START).timestamp())
    end_ts = int(pd.Timestamp(datetime.now()).timestamp())
    params = {
        "ticker": ticker,
        "type": "stock",
        "resolution": "D",
        "from": start_ts,
        "to": end_ts,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CORE-MSRA/1.0)",
        "Accept": "application/json",
    }
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    payload = r.json()

    data = payload.get("data") or []
    if not data:
        raise ValueError(f"TCBS trả rỗng cho {ticker}")

    df = pd.DataFrame(data)
    # TCBS dùng: tradingDate, open, high, low, close, volume
    if "tradingDate" not in df.columns:
        raise ValueError("Thiếu cột tradingDate")
    df = df.rename(columns={
        "tradingDate": "Date",
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = (df.dropna()
            .drop_duplicates(subset=["Date"])
            .sort_values("Date")
            .reset_index(drop=True))
    df = df[df["Volume"] > 0].reset_index(drop=True)
    return df


# ============ PUBLIC API ============
def load_stock(ticker):
    """
    Load daily: cache → TCBS → (fallback nếu cần).
    Signature giữ nguyên để main.py không phải sửa.
    """
    # 1. Cache
    cached = _load_cache(ticker)
    if cached is not None and len(cached) >= 300:
        return cached

    # 2. TCBS
    try:
        df = _load_tcbs(ticker)
        if df is not None and len(df) >= 300:
            df.attrs["source"] = "TCBS"
            _save_cache(ticker, df)
            time.sleep(0.5)  # Lịch sự với server
            return df
        else:
            print(f"  {ticker}: TCBS trả {len(df) if df is not None else 0} bar, cần ≥300")
    except Exception as e:
        print(f"  {ticker}: TCBS lỗi — {str(e)[:80]}")

    # 3. Fallback: dùng cache cũ nếu có (dù hết TTL)
    path = _cache_path(ticker)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, parse_dates=["Date"])
            df.attrs["source"] = "cache_old"
            print(f"  {ticker}: dùng cache cũ ({len(df)} bar)")
            return df
        except Exception:
            pass

    return None


# ============================================================
# INDICATORS — giữ nguyên, đã đúng
# ============================================================
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
    """Luật A1i+50 — giữ nguyên."""
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
