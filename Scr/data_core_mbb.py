# Scr/data_core_mbb.py
# Data fetcher CORE-MBB — daily 1D
# Nguồn: KBS (chính) → VCI (fallback)

import pandas as pd
from datetime import datetime, timedelta
from vnstock import Quote


def get_intraday_data(ticker, days=60):
    """
    Lấy dữ liệu daily 1D cho CORE-MBB.
    - days: số ngày lookback (mặc định 60 đủ cho MA20, ADX14, ROC10)
    - Trả về DataFrame với cột: Date, Open, High, Low, Close, Volume
    - Nếu fail → trả về DataFrame rỗng
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    for source in ["KBS", "VCI"]:
        try:
            q = Quote(source=source, symbol=ticker)
            df = q.history(start=start_str, end=end_str, interval="1D")

            if df is None or len(df) == 0:
                print(f"  [{ticker}][{source}] empty")
                continue

            # Chuẩn hóa cột
            df.columns = [str(c).strip().lower() for c in df.columns]
            rename = {
                "time": "Date", "date": "Date",
                "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume",
            }
            df = df.rename(columns=rename)

            need = ["Date", "Open", "High", "Low", "Close", "Volume"]
            missing = [c for c in need if c not in df.columns]
            if missing:
                print(f"  [{ticker}][{source}] thiếu cột {missing}")
                continue

            df = df[need].copy()
            df["Date"] = pd.to_datetime(df["Date"])
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            df = df.dropna().drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)

            if len(df) < 30:
                print(f"  [{ticker}][{source}] chỉ {len(df)} nến")
                continue

            print(f"  [{ticker}][{source}] OK — {len(df)} nến, cuối {df.iloc[-1]['Date'].date()}")
            return df

        except Exception as e:
            err = str(e)[:100]
            print(f"  [{ticker}][{source}] Fail: {err}")
            continue

    print(f"  [{ticker}] FAIL cả 2 nguồn — trả về rỗng")
    return pd.DataFrame()
