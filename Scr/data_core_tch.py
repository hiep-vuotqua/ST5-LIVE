def _fetch_vci(ticker, start_str, end_str):
    """Lấy dữ liệu lịch sử từ VCI API — hỗ trợ cả 2 format."""
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

    # VCI trả về list chứa 1 dict, hoặc dict trực tiếp
    if isinstance(data, list) and len(data) > 0:
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError(f"VCI format lạ: {type(data)}")

    # Trường hợp 1: cột dọc — {"t": [...], "o": [...], "h": [...], ...}
    if isinstance(data.get("t"), list):
        df = pd.DataFrame({
            "Date": data.get("t", []),
            "Open": data.get("o", []),
            "High": data.get("h", []),
            "Low": data.get("l", []),
            "Close": data.get("c", []),
            "Volume": data.get("v", []),
        })
    # Trường hợp 2: array of objects (phòng khi VCI đổi format)
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

    # Xử lý Date
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
