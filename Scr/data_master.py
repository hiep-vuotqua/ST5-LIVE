import pandas as pd
from datetime import datetime, timedelta
from vnstock import Quote

def get_intraday_data(ticker, days=400):
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
            rn = {"time":"Date","date":"Date","open":"Open","high":"High",
                  "low":"Low","close":"Close","volume":"Volume"}
            df = df.rename(columns={k:v for k,v in rn.items() if k in df.columns})
            df = df[["Date","Open","High","Low","Close","Volume"]].copy()
            df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
            for c in ["Open","High","Low","Close","Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna().drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
            # KHÔNG filter flat — Wilder's EWMA
            if len(df) < 230:
                print(f"  [{ticker}][{source}] chỉ {len(df)} nến < 230, thử nguồn khác")
                continue
            print(f"  [{ticker}][{source}] OK — {len(df)} nến, cuối {df['Date'].iloc[-1].date()}")
            return df
        except Exception as e:
            print(f"  [{ticker}][{source}] Fail: {str(e)[:100]}")
            continue
    print(f"  [{ticker}] FAIL")
    return pd.DataFrame()
