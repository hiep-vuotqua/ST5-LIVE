# data_core_multi.py — copy từ data_core_b3.py (giống hệt)
import pandas as pd
from datetime import datetime
from vnstock.api.quote import Quote

def get_data(ticker, days=500):
    q = Quote(symbol=ticker, source="KBS")
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - pd.Timedelta(days=days*2)).strftime("%Y-%m-%d")
    df = q.history(start=start, end=end, interval="1D")
    df = df.rename(columns={"time": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    df.columns = [c.lower() for c in df.columns]
    df = df.dropna().drop_duplicates()
    return df.tail(days) 
