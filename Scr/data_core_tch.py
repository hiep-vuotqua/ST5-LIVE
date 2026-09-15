# Scr/data_core_tch.py
# Data fetcher CORE-TCH — daily 1D
# Nguồn: VNDIRECT (chính) → KBS (fallback)

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


def _fetch_vndirect(ticker, start_str, end_str):
    """VNDIRECT dchart API — public, không cần key."""
    url = "https://dchart-api.vndirect.com.vn/dchart"
    to_ts = int(pd.Timestamp(end_str).timestamp())
    from_ts = int(pd.Timestamp(start_str).timestamp())
    params = {
        "symbol": ticker,
        "resolution": "D",
        "from": from_ts,
        "to": to_ts,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ST5-TCH/1.0)",
        "Accept": "application/json",
    }
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    payload = r.json()

    if not isinstance(payload, dict) or "t" not in payload:
        raise ValueError(f"VNDIRECT format lạ: {str(payload)[:200]}")

    df = pd.DataFrame({
        "Date": payload.get("t", []),
        "Open": payload.get("o", []),
        "High": payload.get("h", []),
        "Low": payload.get("l", []),
        "Close": payload.get("c", []),
        "Volume": payload.get("v", []),
    })

    if df.empty:
        raise ValueError("VNDIRECT trả rỗng")

    df["Date"] = pd.to_datetime(df["Date"], unit="s")
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = (df.dropna()
            .drop_duplicates(subset=["Date"])
            .sort_values("Date")
            .reset_index(drop=True))
    df = df[df["Volume"] > 0].reset_index(drop=True)
    return df


def _fetch_kbs(ticker, start_str, end_str):
    """KBS fallback — thử API đơn giản."""
    url = "https://kbbuddywts.kbsec.com.vn/iis-server/investment/trade/history"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    params = {
        "symbol": ticker, "startDate": start_str,
        "endDate": end_str, "pageSize": 1000,
    }
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data") or payload.get("content") or []
    if not data:
        raise ValueError("KBS rỗng")
    df = pd.DataFrame(data)
    rename_map = {
        "tradingDate": "Date", "date": "Date", "time": "Date",
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    for c in ["Date", "Open", "High", "Low", "Close", "Volume"]:
        if c not in df.columns:
            raise ValueError(f"KBS thiếu {c}")
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
    """Load: cache → VNDIRECT → KBS → cache cũ."""
    cached = _load_cache(ticker)
    if cached is not None and len(cached) >= 30:
        print(f"  [{ticker}][cache] OK — {len(cached)} nến")
        return cached

    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    # VNDIRECT
    try:
        df = _fetch_vndirect(ticker, start_str, end_str)
        if len(df) >= 30:
            _save_cache(ticker, df)
            time.sleep(0.3)
            print(f"  [{ticker}][VNDIRECT] OK — {len(df)} nến, cuối {df.iloc[-1]['Date'].date()}")
            return df
        else:
            print(f"  [{ticker}][VNDIRECT] chỉ {len(df)} nến")
    except Exception as e:
        print(f"  [{ticker}][VNDIRECT] Fail: {str(e)[:100]}")

    # KBS
    try:
        df = _fetch_kbs(ticker, start_str, end_str)
        if len(df) >= 30:
            _save_cache(ticker, df)
            time.sleep(0.3)
            print(f"  [{ticker}][KBS] OK — {len(df)} nến, cuối {df.iloc[-1]['Date'].date()}")
            return df
        else:
            print(f"  [{ticker}][KBS] chỉ {len(df)} nến")
    except Exception as e:
        print(f"  [{ticker}][KBS] Fail: {str(e)[:100]}")

    # Cache cũ
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
