"""
CORE-30 config — variant B
Ngày chốt: 2026-09-19
Backtest: CAGR 18.56%, MaxDD -5.41%, 7/9 năm dương, 2122 trades
"""

CORE_30 = [
    "ABB", "VIX", "HCM", "NKG", "IDJ", "VPB", "NVL", "CEO", "VDS", "SSI",
    "HCD", "APG", "DIG", "BVS", "MBS", "CTS", "CTR", "PHP", "GEE", "FRT",
    "BSI", "NHA", "CTP", "TVS",
    "FDC", "SVN", "VNA", "VEF", "VSC", "LGL",
]

VOLUME_RATIO_MIN = 1.2
ROC10_MIN        = 3.0
MACD_HIST_MIN    = 0.0
ADX14_MIN        = 16.0
USE_MA200        = False
USE_MA50         = True
MIN_HOLD_DAYS    = 3

TIMEZONE              = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND         = 0.4
STATE_FILE            = "../data/live_state_core_30.json"
TELEGRAM_TITLE        = "ST5 CORE-30"
DELAY_BETWEEN_TICKERS = 3
