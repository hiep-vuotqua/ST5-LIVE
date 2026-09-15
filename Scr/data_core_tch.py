# Scr/data_core_tch.py
# Data fetcher CORE-TCH — daily 1D
# Nguồn: vnstock (KBS -> VCI)

import time
import pandas as pd
from datetime import datetime, timedelta

# Import vnstock
try:
    from vnstock import Vnstock
    VNSTOCK_OK = True
except Exception as e:
    VNSTOCK_OK = False
    print(f"  [CẢNH BÁO] Không import được vnstock: {e}")


def _fetch_vnstock(ticker, start_str, end_str):
    """Lấy dữ liệu lịch sử từ vnstock — API mới (vnstock.api.quote)."""
    for source in ["KBS", "VCI"]:
        try:
            from vnstock.api.quote import Quote
            q = Quote(symbol=ticker, source=source)
            df = q.history(start=start_str, end=end_str, interval="1D")

            if df is None or len(df) == 0:
                print(f"  [{ticker}][{source}] trả về rỗng")
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
                print(f"  [{ticker}][{source}] thiếu cột: {df.columns.tolist()}")
                continue

            df = df[need].copy()
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            df = (df.dropna()
                    .drop_duplicates(subset=["Date"])
                    .sort_values("Date")
                    .reset_index(drop=True))
            df = df[df["Volume"] > 0].reset_index(drop=True)

            if len(df) < 30:
                print(f"  [{ticker}][{source}] chỉ {len(df)} nến")
                continue

            time.sleep(0.5)
            print(f"  [{ticker}][{source}] OK — {len(df)} nến, cuối {df.iloc[-1]['Date'].date()}")
            return df

        except Exception as e:
            print(f"  [{ticker}][{source}] Fail: {str(e)[:100]}")
            continue

    raise ValueError("Tất cả nguồn vnstock đều thất bại")


def get_intraday_data(ticker, days=400):
    """
    Lấy dữ liệu daily 1D cho CORE-TCH.
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    try:
        df = _fetch_vnstock(ticker, start_str, end_str)
        return df
    except Exception as e:
        print(f"  [{ticker}] THẤT BẠI HOÀN TOÀN: {e}")
        return pd.DataFrame()
