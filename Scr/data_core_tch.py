# Scr/data_core_tch.py
# Data fetcher CORE-TCH — daily 1D
# Nguồn: TCBS public API (không cần key, không rate limit)

import os
import time
import pandas as pd
import requests
from datetime import datetime, timedelta

CACHE_DIR = "cache_data_tch"
CACHE_TTL_HOURS = 4


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
        return df
    except Exception:
        return None


def _save_cache(ticker, df):
    try:
        df.to_csv(_cache_path(ticker), index=False)
    except Exception:
        pass


def _fetch_tcbs(ticker, start_str, end_str):
    url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
    start_ts = int(pd.Timestamp(start_str).timestamp())
    end_ts = int(pd.Timestamp(end_str).timestamp())
    params = {
        "ticker": ticker, "type": "stock", "resolution": "D",
        "from": start_ts, "to": end_ts,
    }
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ST5-TCH/1.0)"}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data") or []
    if not data:
        raise ValueError("TCBS trả rỗng")

    df = pd.DataFrame(data)
    if "tradingDate" not in df.columns:
        raise ValueError("Thiếu cột tradingDate")

    df = df.rename(columns={
        "tradingDate": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume",
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


def get_intraday_data(ticker, days=400):
    """
    Lấy dữ liệu daily 1D cho CORE-TCH.
    Nguồn: cache → TCBS → cache cũ.
    """
    # 1. Cache
    cached = _load_cache(ticker)
    if cached is not None and len(cached) >= 30:
        print(f"  [{ticker}][cache] OK — {len(cached)} nến")
        return cached

    # 2. TCBS
    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    try:
        df = _fetch_tcbs(ticker, start_str, end_str)
        if len(df) >= 30:
            _save_cache(ticker, df)
            time.sleep(0.3)
            print(f"  [{ticker}][TCBS] OK — {len(df)} nến, cuối {df.iloc[-1]['Date'].date()}")
            return df
        else:
            print(f"  [{ticker}][TCBS] chỉ {len(df)} nến")
    except Exception as e:
        print(f"  [{ticker}][TCBS] Fail: {str(e)[:100]}")

    # 3. Cache cũ (dù hết TTL)
    path = _cache_path(ticker)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, parse_dates=["Date"])
            print(f"  [{ticker}][cache_old] {len(df)} nến")
            return df
        except Exception:
            pass

    print(f"  [{ticker}] FAIL — trả về rỗng")
    return pd.DataFrame()
