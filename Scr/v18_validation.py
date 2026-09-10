import sys
import time
import pandas as pd

from data import get_intraday_data
from indicators import add_v14_indicators


# ============================================================
# ST5 V1.8 — 5M VALIDATION
# FINAL LIVE CANDIDATES = 33 MÃ
#
# KHÔNG TELEGRAM
# KHÔNG STATE
# KHÔNG GIAO DỊCH
# KHÔNG SỬA V1.4
# ============================================================

V18_SYMBOLS = [

    # ========================================================
    # WINNER — 16
    # ========================================================
    "THD", "VIB", "PVD", "SSI", "SHS", "KBC",
    "VCI", "HPG", "VIX", "SIP", "PLX", "ABB",
    "API", "VPB", "CII", "AAS",

    # ========================================================
    # STRONG — 10
    # ========================================================
    "CEO", "APG", "ACV", "KDC", "DXG",
    "VCG", "NKG", "EVF", "DGC", "ADS",

    # ========================================================
    # WATCH — 7
    # ========================================================
    "GMD", "NAF", "POW", "MBB", "SHB", "HDB", "DPM",
]


WINNER = {
    "THD", "VIB", "PVD", "SSI", "SHS", "KBC",
    "VCI", "HPG", "VIX", "SIP", "PLX", "ABB",
    "API", "VPB", "CII", "AAS",
}

STRONG = {
    "CEO", "APG", "ACV", "KDC", "DXG",
    "VCG", "NKG", "EVF", "DGC", "ADS",
}

WATCH = {
    "GMD", "NAF", "POW", "MBB", "SHB", "HDB", "DPM",
}


# ============================================================
# V1.8 FROZEN
# ============================================================

def v18_entry(df):
    return (
        (df["ADX14"] > 40.0)
        &
        (df["MACD_HIST_SLOPE"] > 0.0)
    )


def v18_exit(df):
    return (
        (df["MACD_Hist"] <= 0.0)
        |
        (df["ROC10"] <= 2.0)
        |
        (df["ADX14"] <= 30.0)
    )


def classify(ticker):
    if ticker in WINNER:
        return "WINNER"

    if ticker in STRONG:
        return "STRONG"

    if ticker in WATCH:
        return "WATCH"

    return "UNKNOWN"


def prepare_indicators(df):
    """
    Dùng indicator engine hiện tại của ST5:
        ROC10
        MACD_Hist
        ADX14

    Sau đó bổ sung:
        MACD_HIST_SLOPE = MACD_Hist.diff()

    Không thay đổi công thức V1.4 hiện tại.
    """

    df = df.copy()

    df = add_v14_indicators(df)

    df["MACD_HIST_SLOPE"] = (
        df["MACD_Hist"].diff()
    )

    return df


def validate_one(ticker):

    result = {
        "ticker": ticker,
        "class": classify(ticker),
        "status": "FAIL",
        "rows": 0,
        "first_date": "",
        "last_date": "",
        "latest_price": None,
        "latest_adx": None,
        "latest_macd_hist": None,
        "latest_macd_slope": None,
        "latest_roc10": None,
        "latest_entry": False,
        "latest_exit": False,
        "entry_count": 0,
        "exit_count": 0,
        "data_error": "",
    }

    print()
    print("=" * 80)
    print(f"{ticker} — {classify(ticker)}")
    print("=" * 80)

    try:

        # ----------------------------------------------------
        # LOAD 5M
        # ----------------------------------------------------
        df = get_intraday_data(
            ticker,
            days=5,
            retries=3
        )

        if df is None or df.empty:
            result["data_error"] = "EMPTY_DATA"
            print("❌ Không có dữ liệu")
            return result

        # ----------------------------------------------------
        # BASIC DATA CHECK
        # ----------------------------------------------------
        required = [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        missing = [
            c for c in required
            if c not in df.columns
        ]

        if missing:
            result["data_error"] = (
                f"MISSING_COLUMNS:{missing}"
            )
            print("❌ Thiếu cột:", missing)
            return result

        df = df.sort_values("Date").copy()

        df = df.drop_duplicates(
            subset=["Date"],
            keep="last"
        )

        result["rows"] = len(df)

        if len(df) == 0:
            result["data_error"] = "NO_ROWS"
            print("❌ Không còn dòng dữ liệu")
            return result

        result["first_date"] = str(
            df["Date"].iloc[0]
        )

        result["last_date"] = str(
            df["Date"].iloc[-1]
        )

        # ----------------------------------------------------
        # PRICE SANITY
        # ----------------------------------------------------
        for col in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:

            if not pd.api.types.is_numeric_dtype(
                df[col]
            ):
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

        if df[
            [
                "Open",
                "High",
                "Low",
                "Close",
            ]
        ].isna().any().any():

            result["data_error"] = "NULL_OHLC"
            print("❌ Có OHLC null")
            return result

        if (
            df[
                [
                    "Open",
                    "High",
                    "Low",
                    "Close",
                ]
            ] <= 0
        ).any().any():

            result["data_error"] = "NONPOSITIVE_PRICE"
            print("❌ Có giá <= 0")
            return result

        if (df["Volume"] < 0).any():

            result["data_error"] = "NEGATIVE_VOLUME"
            print("❌ Có volume âm")
            return result

        # ----------------------------------------------------
        # INDICATORS
        # ----------------------------------------------------
        df = prepare_indicators(df)

        indicator_cols = [
            "ROC10",
            "MACD_Hist",
            "MACD_HIST_SLOPE",
            "ADX14",
        ]

        df = df.dropna(
            subset=indicator_cols
        ).copy()

        if df.empty:
            result["data_error"] = (
                "NO_VALID_INDICATOR_ROWS"
            )
            print("❌ Không đủ dữ liệu indicator")
            return result

        # ----------------------------------------------------
        # V1.8 SIGNALS
        # ----------------------------------------------------
        df["ENTRY"] = v18_entry(df)
        df["EXIT"] = v18_exit(df)

        # ----------------------------------------------------
        # COUNTS
        # ----------------------------------------------------
        result["entry_count"] = int(
            df["ENTRY"].sum()
        )

        result["exit_count"] = int(
            df["EXIT"].sum()
        )

        # ----------------------------------------------------
        # LATEST ROW
        # ----------------------------------------------------
        row = df.iloc[-1]

        result["latest_price"] = float(
            row["Close"]
        )

        result["latest_adx"] = float(
            row["ADX14"]
        )

        result["latest_macd_hist"] = float(
            row["MACD_Hist"]
        )

        result["latest_macd_slope"] = float(
            row["MACD_HIST_SLOPE"]
        )

        result["latest_roc10"] = float(
            row["ROC10"]
        )

        result["latest_entry"] = bool(
            row["ENTRY"]
        )

        result["latest_exit"] = bool(
            row["EXIT"]
        )

        result["status"] = "PASS"

        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------
        print(
            f"Rows              : {result['rows']}"
        )

        print(
            f"Range             : "
            f"{result['first_date']} → "
            f"{result['last_date']}"
        )

        print(
            f"Latest Price      : "
            f"{result['latest_price']:.2f}"
        )

        print(
            f"Latest ADX14      : "
            f"{result['latest_adx']:.4f}"
        )

        print(
            f"Latest MACD Hist  : "
            f"{result['latest_macd_hist']:.6f}"
        )

        print(
            f"MACD Hist Slope   : "
            f"{result['latest_macd_slope']:.6f}"
        )

        print(
            f"ROC10             : "
            f"{result['latest_roc10']:.4f}%"
        )

        print(
            f"5M ENTRY count    : "
            f"{result['entry_count']}"
        )

        print(
            f"5M EXIT count     : "
            f"{result['exit_count']}"
        )

        print(
            f"LATEST ENTRY      : "
            f"{'YES' if result['latest_entry'] else 'NO'}"
        )

        print(
            f"LATEST EXIT       : "
            f"{'YES' if result['latest_exit'] else 'NO'}"
        )

        print(
            f"STATUS            : ✅ PASS"
        )

        return result

    except Exception as e:

        result["data_error"] = (
            f"{type(e).__name__}: {e}"
        )

        print(
            f"❌ ERROR: "
            f"{type(e).__name__}: {e}"
        )

        return result


def main():

    print()
    print("=" * 90)
    print("ST5 V1.8 — 5M VALIDATION")
    print("=" * 90)

    print()
    print("V1.8 RULE — ENTRY")
    print(
        "ADX14 > 40 "
        "AND "
        "MACD_HIST_SLOPE > 0"
    )

    print()
    print("V1.8 RULE — EXIT")
    print(
        "MACD_Hist <= 0 "
        "OR ROC10 <= 2 "
        "OR ADX14 <= 30"
    )

    print()
    print(f"TOTAL SYMBOLS: {len(V18_SYMBOLS)}")

    if len(V18_SYMBOLS) != 33:
        print(
            "❌ ERROR: "
            "V18_SYMBOLS không đủ 33 mã"
        )
        sys.exit(1)

    # --------------------------------------------------------
    # CHECK DUPLICATE SYMBOL
    # --------------------------------------------------------
    duplicates = [
        x for x in V18_SYMBOLS
        if V18_SYMBOLS.count(x) > 1
    ]

    if duplicates:

        print(
            "❌ DUPLICATE SYMBOLS:",
            sorted(set(duplicates))
        )

        sys.exit(1)

    # --------------------------------------------------------
    # CHECK CLASS COUNTS
    # --------------------------------------------------------
    print()
    print("CLASS COUNT")
    print("-" * 50)

    print(
        f"WINNER : {len(WINNER)}"
    )

    print(
        f"STRONG : {len(STRONG)}"
    )

    print(
        f"WATCH  : {len(WATCH)}"
    )

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------
    results = []

    for i, ticker in enumerate(
        V18_SYMBOLS,
        start=1
    ):

        print()
        print(
            f"[{i}/{len(V18_SYMBOLS)}] "
            f"Processing {ticker}"
        )

        result = validate_one(ticker)

        results.append(result)

        # tránh rate-limit KBS
        if i < len(V18_SYMBOLS):
            time.sleep(2)

    # --------------------------------------------------------
    # DATAFRAME
    # --------------------------------------------------------
    result_df = pd.DataFrame(results)

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------
    passed = result_df[
        result_df["status"] == "PASS"
    ]

    failed = result_df[
        result_df["status"] != "PASS"
    ]

    print()
    print()
    print("=" * 90)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 90)

    print()
    print(
        f"TOTAL      : {len(result_df)}"
    )

    print(
        f"PASS       : {len(passed)}"
    )

    print(
        f"FAIL       : {len(failed)}"
    )

    print()

    if len(failed) > 0:

        print("FAILED SYMBOLS")
        print("-" * 50)

        for _, row in failed.iterrows():

            print(
                f"{row['ticker']} | "
                f"{row['class']} | "
                f"{row['data_error']}"
            )

    print()
    print("=" * 90)
    print("LATEST V1.8 SIGNAL SNAPSHOT")
    print("=" * 90)

    if len(passed) > 0:

        display_cols = [
            "ticker",
            "class",
            "rows",
            "latest_price",
            "latest_adx",
            "latest_macd_hist",
            "latest_macd_slope",
            "latest_roc10",
            "latest_entry",
            "latest_exit",
            "entry_count",
            "exit_count",
        ]

        print(
            passed[
                display_cols
            ].to_string(
                index=False
            )
        )

    print()
    print("=" * 90)
    print("V1.8 5M VALIDATION COMPLETE")
    print("=" * 90)

    # --------------------------------------------------------
    # EXIT CODE
    # --------------------------------------------------------
    if len(failed) > 0:

        print()
        print(
            "⚠️ CÓ MÃ FAIL — "
            "CHƯA ĐƯA V1.8 VÀO LIVE."
        )

        sys.exit(2)

    print()
    print(
        "✅ 33/33 DATA + INDICATOR ENGINE PASS"
    )

    print(
        "ℹ️ Đây là VALIDATION ENGINE, "
        "KHÔNG phải backtest hiệu quả 5M."
    )

    print(
        "ℹ️ Chưa gửi Telegram."
    )

    print(
        "ℹ️ Chưa tạo/ghi state."
    )


if __name__ == "__main__":
    main() 
