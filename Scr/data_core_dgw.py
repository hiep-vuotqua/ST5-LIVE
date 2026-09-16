# ============================================================
# ST5-LIVE — DATA CORE-DGW
# KBS + CACHE 4 HOURS
# Daily 1D
# ============================================================

import os
import time
import pandas as pd

from vnstock.api.quote import Quote


CACHE_DIR = "cache_data_dgw"
CACHE_TTL_HOURS = 4

REQUEST_INTERVAL = 3.5

_last_request = 0.0

os.makedirs(CACHE_DIR, exist_ok=True)


# ============================================================
# CACHE
# ============================================================

def _cache_path(ticker):
    return os.path.join(
        CACHE_DIR,
        f"{ticker.upper()}.csv"
    )


def _load_cache(ticker):
    path = _cache_path(ticker)

    if not os.path.exists(path):
        return None

    try:
        age_hours = (
            time.time() - os.path.getmtime(path)
        ) / 3600

        if age_hours > CACHE_TTL_HOURS:
            return None

        df = pd.read_csv(path)

        if df is None or len(df) == 0:
            return None

        return _normalize(df)

    except Exception:
        return None


def _save_cache(ticker, df):
    df.to_csv(
        _cache_path(ticker),
        index=False
    )


# ============================================================
# NORMALIZE
# ============================================================

def _normalize(df):
    if df is None or len(df) == 0:
        return pd.DataFrame()

    df = df.copy()

    rename = {}

    for c in df.columns:
        x = str(c).lower().strip()

        if x in ["time", "date", "datetime"]:
            rename[c] = "Date"

        elif x == "open":
            rename[c] = "Open"

        elif x == "high":
            rename[c] = "High"

        elif x == "low":
            rename[c] = "Low"

        elif x in ["close", "price"]:
            rename[c] = "Close"

        elif x in ["volume", "vol"]:
            rename[c] = "Volume"

    df = df.rename(columns=rename)

    required = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    if not all(
        c in df.columns
        for c in required
    ):
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    for c in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]:
        df[c] = pd.to_numeric(
            df[c],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )

    df = (
        df.sort_values("Date")
          .drop_duplicates("Date")
          .reset_index(drop=True)
    )

    return df


# ============================================================
# RATE LIMIT
# ============================================================

def _wait():
    global _last_request

    wait = (
        REQUEST_INTERVAL
        - (time.time() - _last_request)
    )

    if wait > 0:
        time.sleep(wait)


# ============================================================
# STOCK DATA
# ============================================================

def get_intraday_data(ticker, days=400):

    global _last_request

    ticker = ticker.upper().strip()

    cached = _load_cache(ticker)

    if cached is not None and len(cached) >= 30:
        print(
            f"  [{ticker}] CACHE OK — "
            f"{len(cached)} rows"
        )
        return cached

    print(
        f"  [{ticker}] KBS API..."
    )

    _wait()

    q = Quote(
        symbol=ticker,
        source="KBS"
    )

    end_date = pd.Timestamp.today().strftime(
        "%Y-%m-%d"
    )

    df = q.history(
        start="2018-01-01",
        end=end_date,
        interval="1D"
    )

    _last_request = time.time()

    df = _normalize(df)

    if len(df) > 0:
        _save_cache(ticker, df)

    return df


# ============================================================
# VNINDEX
# ============================================================

def get_vnindex():

    global _last_request

    cache_file = os.path.join(
        CACHE_DIR,
        "VNINDEX.csv"
    )

    if os.path.exists(cache_file):

        try:
            age_hours = (
                time.time()
                - os.path.getmtime(cache_file)
            ) / 3600

            if age_hours <= CACHE_TTL_HOURS:

                df = pd.read_csv(
                    cache_file
                )

                df = _normalize(df)

                if len(df) >= 30:
                    print(
                        "  [VNINDEX] CACHE OK"
                    )
                    return df

        except Exception:
            pass

    print(
        "  [VNINDEX] KBS API..."
    )

    _wait()

    q = Quote(
        symbol="VNINDEX",
        source="KBS"
    )

    end_date = pd.Timestamp.today().strftime(
        "%Y-%m-%d"
    )

    df = q.history(
        start="2018-01-01",
        end=end_date,
        interval="1D"
    )

    _last_request = time.time()

    df = _normalize(df)

    if len(df) > 0:
        df.to_csv(
            cache_file,
            index=False
        )

    return df 
