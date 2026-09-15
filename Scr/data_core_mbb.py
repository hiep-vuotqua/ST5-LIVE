# Scr/data_core_mbb.py
# Data fetcher CORE-MBB — daily 1D
# Nguồn: KBS (chính) + cache. Không fallback để tránh rate limit.

import os
import time
import pandas as pd
from datetime import datetime, timedelta

CACHE_DIR = "cache_data_mbb"
CACHE_TTL_HOURS = 4

try:
    from vnstock.api.quote import Quote
    VNSTOCK_OK = True
except Exception as e:
    VNSTOCK_OK = False
    print(f"  [CẢNH BÁO] Không import được vnstock: {e}")


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


def get_intraday_data(ticker, days=400):
    """
    Lấy dữ liệu daily 1D cho CORE-MBB.
    Nguồn: cache → KBS → cache cũ.
    """
    if not VNSTOCK_OK:
        return pd.DataFrame()

    # 1. Cache
    cached = _load_cache(ticker)
    if cached is not None and len(cached) >= 30:
        return cached

    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    # 2. KBS (chỉ 1 nguồn)
    try:
        q = Quote(symbol=ticker, source="KBS")
        df = q.history(start=start_str, end=end_str, interval="1D")

        if df is not None and len(df) > 0:
            df.columns = [str(c).strip().lower() for c in df.columns]
            rename = {
                "time": "Date", "date": "Date",
                "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume",
            }
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

            need = ["Date", "Open", "High", "Low", "Close", "Volume"]
            if all(c in df.columns for c in need):
                df = df[need].copy()
                df["Date"] = pd.to_datetime(df["Date"])
                for c in ["Open", "High", "Low", "Close", "Volume"]:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                df = (df.dropna()
                        .drop_duplicates(subset=["Date"])
                        .sort_values("Date")
                        .reset_index(drop=True))
                df = df[df["Volume"] > 0].reset_index(drop=True)

                if len(df) >= 30:
                    _save_cache(ticker, df)
                    df.attrs["source"] = "KBS"
                    time.sleep(3.5)
                    print(f"  [{ticker}][KBS] OK — {len(df)} nến, cuối {df.iloc[-1]['Date'].date()}")
                    return df
    except Exception as e:
        print(f"  [{ticker}][KBS] Fail: {str(e)[:80]}")
        time.sleep(5)

    # 3. Cache cũ
    path = _cache_path(ticker)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, parse_dates=["Date"])
            df.attrs["source"] = "cache_old"
            print(f"  [{ticker}][cache_old] {len(df)} nến")
            return df
        except Exception:
            pass

    print(f"  [{ticker}] FAIL — trả về rỗng")
    return pd.DataFrame()
