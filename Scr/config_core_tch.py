# Scr/data_core_tch.py
# Data fetcher RIÊNG cho CORE-TCH
# - Timeout ngắn (10s KBS, 5s VCI)
# - Không retry loop dài (1 lần/nguồn)
# - Cache 60s
# - Fallback KBS → VCI
# - Trả về DataFrame cùng schema với data.py

import time
import os
import pandas as pd
from datetime import datetime, timedelta
from vnstock import Quote


# ===== CACHE =====
CACHE_DIR = "data/cache_core_tch"
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
    try:
        return pd.read_csv(_cache_path(ticker), parse_dates=["Date"])
    except Exception:
        return None


def _write_cache(ticker, df):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        df.to_csv(_cache_path(ticker), index=False)
    except Exception as e:
        print(f"  [cache] {ticker}: {e}")


# ===== HÀM CHÍNH =====
def get_intraday_data(ticker, days=5, retries=1):
    """
    Lấy dữ liệu intraday 5M cho ticker — phiên bản CORE-TCH.
    
    Khác biệt so với data.py chung:
    - Cache 60s (không gọi API nếu vừa lấy)
    - Chỉ 1 lần thử/nguồn (không retry loop)
    - Fallback KBS → VCI
    - Trả về DataFrame rỗng nếu fail (tương thích với main_core_tch)
    
    Tham số:
        ticker: mã cổ phiếu
        days: số ngày lookback
        retries: giữ để tương thích signature, không dùng
    
    Trả về:
        DataFrame với cột [Date, Open, High, Low, Close, Volume]
        hoặc DataFrame rỗng nếu fail
    """
    # ===== CACHE =====
    if _is_cache_valid(ticker):
        cached = _read_cache(ticker)
        if cached is not None and len(cached) >= 30:
            return cached

    end = pd.Timestamp.now()
    start = end - pd.Timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    # ===== THỬ LẦN LƯỢT KBS → VCI =====
    for source in ["KBS", "VCI"]:
        try:
            quote = Quote(symbol=ticker, source=source)
            df = quote.history(
                start=start_str,
                end=end_str,
                interval="5m"
            )

            if df is None or df.empty:
                print(f"  [{ticker}][{source}] empty")
                continue

            # Chuẩn hóa cột
            df.columns = [str(c).strip().lower() for c in df.columns]
            rename = {
                "time": "Date", "datetime": "Date", "date": "Date",
                "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume",
            }
            df = df.rename(columns=rename)

            required = ["Date", "Open", "High", "Low", "Close", "Volume"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                print(f"  [{ticker}][{source}] thiếu cột {missing}")
                continue

            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            for c in required[1:]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            df = df.dropna(subset=required)
            df = df.sort_values("Date").drop_duplicates(subset=["Date"])

            if len(df) < 30:
                print(f"  [{ticker}][{source}] chỉ {len(df)} dòng")
                continue

            df = df.reset_index(drop=True)
            _write_cache(ticker, df)
            print(f"  [{ticker}][{source}] OK — {len(df)} dòng")
            return df

        except Exception as e:
            err_type = type(e).__name__
            err_msg = str(e)[:80]
            print(f"  [{ticker}][{source}] {err_type}: {err_msg}")
            continue

    # ===== CẢ 2 NGUỒN FAIL =====
    print(f"  [{ticker}] FAIL — trả về DataFrame rỗng")
    return pd.DataFrame()
