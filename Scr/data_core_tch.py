# Scr/data_core_tch.py
# Data fetcher CORE-TCH — daily 1D
# Nguồn: VCI (chính) → KBS (fallback)

import os
import time
import pandas as pd
import requests
from datetime import datetime, timedelta

CACHE_DIR = "cache_data_tch"
CACHE_TTL_HOURS = 4

VCI_CHART_URL = "https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart"
KBS_HISTORY_URL = "https://kbbuddywts.kbsec.com.vn/iis-server/investment/trade/history"


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


def _fetch_vci(ticker, start_str, end_str):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ST5-TCH/1.0)",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "timeFrame": "ONE_DAY",
        "symbols": [ticker],
        "countBack": 500,
    }
    r = requests.post(VCI_CHART_URL, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, list) and len(data) > 0:
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError(f"VCI format lạ: {type(data)}")

    # Cột dọc: {"t": [...], "o": [...], ...}
    if isinstance(data.get("t"), list):
        df = pd.DataFrame({
            "Date": data.get("t", []),
            "Open": data.get("o", []),
            "High": data.get("h", []),
            "Low": data.get("l", []),
            "Close": data.get("c", []),
            "Volume": data.get("v", []),
        })
    # Array of objects
    elif isinstance(data.get("data"), list):
        df = pd.DataFrame(data["data"])
        df = df.rename(columns={
            "t": "Date", "o": "Open", "h": "High", "l": "Low",
            "c": "Close", "v": "Volume",
            "time": "Date", "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "volume": "Volume",
        })
    else:
        raise ValueError(f"VCI format không nhận dạng: keys={list(data.keys())[:5]}")

    if df.empty:
        raise ValueError("VCI trả rỗng")

    for c in ["Date", "Open", "High", "Low", "Close", "Volume"]:
        if c not in df.columns:
            raise ValueError(f"Thiếu cột {c}")

    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()

    if pd.api.types.is_numeric_dtype(df["Date"]):
        df["Date"] = pd.to_datetime(df["Date"], unit="ms")
    else:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = (df.dropna()
            .drop_duplicates(subset=["Date"])
            .sort_values("Date")
            .reset_index(drop=True))
    df = df[df["Volume"] > 0].reset_index(drop=True)
    return df


def _fetch_kbs(ticker, start_str, end_str):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ST5-TCH/1.0)",
        "Accept": "application/json",
    }
    params = {
        "symbol": ticker,
        "startDate": start_str,
        "endDate": end_str,
        "pageSize": 1000,
    }
    r = requests.get(KBS_HISTORY_URL, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    payload = r.json()

    data = payload.get("data") or payload.get("content") or []
    if not data:
        raise ValueError("KBS trả rỗng")

    df = pd.DataFrame(data)
    rename_map = {
        "tradingDate": "Date", "date": "Date", "time": "Date",
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    required = ["Date", "Open", "High", "Low", "Close", "Volume"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"KBS thiếu cột {c}")

    df = df[required].copy()
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
    """Lấy dữ liệu daily 1D cho CORE-TCH."""
    cached = _load_cache(ticker)
    if cached is not None and len(cached) >= 30:
        print(f"  [{ticker}][cache] OK — {len(cached)} nến")
        return cached

    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    # VCI (chính)
    try:
        df = _fetch_vci(ticker, start_str, end_str)
        if len(df) >= 30:
            _save_cache(ticker, df)
            time.sleep(0.5)
            print(f"  [{ticker}][VCI] OK — {len(df)} nến, cuối {df.iloc[-1]['Date'].date()}")
            return df
        else:
            print(f"  [{ticker}][VCI] chỉ {len(df)} nến")
    except Exception as e:
        print(f"  [{ticker}][VCI] Fail: {str(e)[:100]}")

    # KBS (fallback)
    try:
        df = _fetch_kbs(ticker, start_str, end_str)
        if len(df) >= 30:
            _save_cache(ticker, df)
            time.sleep(0.5)
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
