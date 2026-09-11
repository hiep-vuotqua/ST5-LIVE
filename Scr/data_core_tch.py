# Scr/data.py
import pandas as pd
import numpy as np
import requests
import os
import time
from vnstock import Quote

# ===== CACHE =====
CACHE_DIR = "data/cache"
CACHE_TTL = 60  # giây

def _cache_path(ticker):
    return f"{CACHE_DIR}/{ticker}.csv"

def _is_cache_valid(ticker):
    path = _cache_path(ticker)
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < CACHE_TTL

def _read_cache(ticker):
    return pd.read_csv(_cache_path(ticker), parse_dates=["Date"])

def _write_cache(ticker, df):
    os.makedirs(CACHE_DIR, exist_ok=True)
    df.to_csv(_cache_path(ticker), index=False)


def get_intraday_data(ticker, days=20, timeout=10):
    """
    Lấy dữ liệu intraday 5M cho ticker.
    - Timeout: 10s cho KBS, 5s cho VCI
    - Không retry (SKIP nếu fail)
    - Fallback: KBS → VCI
    - Cache: 60s
    """
    # Kiểm tra cache trước
    if _is_cache_valid(ticker):
        return _read_cache(ticker)

    # Nguồn ưu tiên
    for source, source_timeout in [("KBS", timeout), ("VCI", 5)]:
        try:
            q = Quote(source=source, symbol=ticker)
            df = q.history(
                start=_date_n_days_ago(days),
                end=_today(),
                interval="5m"
            )

            if df is None or len(df) == 0:
                continue

            # Chuẩn hóa
            rename = {"time":"Date","date":"Date","open":"Open","high":"High",
                      "low":"Low","close":"Close","volume":"Volume"}
            df = df.rename(columns={k:v for k,v in rename.items() if k in df.columns})

            need = ["Date","Open","High","Low","Close","Volume"]
            if not all(c in df.columns for c in need):
                continue

            df = df[need].copy()
            df["Date"] = pd.to_datetime(df["Date"])
            for c in ["Open","High","Low","Close","Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            df = df.dropna().drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)

            if len(df) < 30:
                continue

            _write_cache(ticker, df)
            return df

        except Exception as e:
            err_str = str(e)[:100]
            print(f"  [{ticker}][{source}] Fail: {err_str}")
            continue

    # Cả 2 nguồn fail → trả về None
    return None


def _date_n_days_ago(n):
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")

def _today():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d") 
