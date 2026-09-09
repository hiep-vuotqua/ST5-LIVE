import time
import pandas as pd
from vnstock import Quote


def get_intraday_data(ticker, days=5, retries=3):
    end = pd.Timestamp.now()
    start = end - pd.Timedelta(days=days)

    last_error = None

    for attempt in range(retries):
        try:
            quote = Quote(
                symbol=ticker,
                source="KBS"
            )

            df = quote.history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval="5m"
            )

            if df is None or df.empty:
                return pd.DataFrame()

            df.columns = [
                str(c).strip().lower()
                for c in df.columns
            ]

            rename = {
                "time": "Date",
                "datetime": "Date",
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }

            df = df.rename(columns=rename)

            required = [
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]

            missing = [
                col for col in required
                if col not in df.columns
            ]

            if missing:
                raise ValueError(
                    f"{ticker}: thiếu cột {missing}"
                )

            df["Date"] = pd.to_datetime(
                df["Date"],
                errors="coerce"
            )

            for col in required[1:]:
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

            df = df.dropna(
                subset=required
            )

            df = df.sort_values("Date")

            df = df.drop_duplicates(
                subset=["Date"]
            )

            return df.reset_index(drop=True)

        except Exception as e:
            last_error = e

            print(
                f"⚠️ {ticker}: "
                f"attempt {attempt + 1}/{retries}: "
                f"{type(e).__name__}: {e}"
            )

            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))

    print(
        f"❌ {ticker}: thất bại sau "
        f"{retries} lần: {last_error}"
    )

    return pd.DataFrame() 
