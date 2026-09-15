import requests
import pandas as pd
from datetime import datetime

def _fetch_vndirect(ticker, start_str, end_str, count_back=500):
    """
    Lấy dữ liệu lịch sử từ VNDIRECT API (dchart-api).
    Không cần API key, không rate limit.
    """
    base_url = "https://dchart-api.vndirect.com.vn/dchart"
    
    # VNDIRECT dùng 'D' cho khung daily và cần 'from', 'to' là timestamp (giây)
    try:
        to_ts = int(pd.Timestamp(end_str).timestamp())
        from_ts = int(pd.Timestamp(start_str).timestamp())
    except Exception as e:
        raise ValueError(f"Ngày không hợp lệ: {e}")

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

    r = requests.get(base_url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    payload = r.json()

    # VNDIRECT trả về {'t': [...], 'o': [...], 'h': [...], 'l': [...], 'c': [...], 'v': [...]}
    if not isinstance(payload, dict) or 't' not in payload:
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
        raise ValueError("VNDIRECT trả về rỗng")

    # Chuyển đổi timestamp (giây) sang datetime
    df["Date"] = pd.to_datetime(df["Date"], unit="s")

    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = (df.dropna()
            .drop_duplicates(subset=["Date"])
            .sort_values("Date")
            .reset_index(drop=True))
    df = df[df["Volume"] > 0].reset_index(drop=True)
    return df
