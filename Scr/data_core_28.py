"""Data fetcher — KBS daily + VCI fallback."""

import pandas as pd
from datetime import datetime, timedelta
from vnstock import Quote


def get_intraday_data(ticker, days=120):
    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")

    for source in ["KBS", "VCI"]:
        try:
            q = Quote(source=source, symbol=ticker)
            df = q.history(start=start_str, end=end_str, interval="1D")
            if df is None or len(df) == 0:
                continue
            df.columns = [str(c).strip().lower() for c in df.columns]
            rename = {
                "time": "Date", "date": "Date",
                "open": "Open", "high": "High",
                "low": "Low",   "close": "Close",
                "volume": "Volume",
            }
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
            need = ["Date", "Open", "High", "Low", "Close", "Volume"]
            if not all(c in df.columns for c in need):
                continue
            df = df[need].copy()
            df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            # KHÔNG filter flat / Volume=0 (BẪY #1 playbook)
            df = (df.dropna()
                    .drop_duplicates(subset=["Date"])
                    .sort_values("Date")
                    .reset_index(drop=True))
            if len(df) < 30:
                continue
            print(f"  [{ticker}][{source}] OK — {len(df)} nến, cuối {df.iloc[-1]['Date'].date()}")
            return df
        except Exception as e:
            print(f"  [{ticker}][{source}] Fail: {str(e)[:100]}")
            continue
    print(f"  [{ticker}] FAIL — trả về rỗng")
    return pd.DataFrame()
