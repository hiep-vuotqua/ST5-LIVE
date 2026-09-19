"""
CORE-31 config — variant B (bỏ MA200, VolR>1.2, ROC10>3, ADX>16, Close>MA50)
Ngày chốt: 2026-09-19
Backtest: CAGR 19.48%, MaxDD -2.61%, 1858 trades / 8.2 năm
Gồm 30 mã Top + SSI.
"""

CORE_31 = [
    "SCI", "PTC", "KDC", "CSC", "PSB", "VFG", "APS", "HCM", "VIX", "LHC",
    "VLG", "MHC", "KDM", "HLD", "ABB", "LGL", "VEF", "IDJ", "TCO", "CMS",
    "TMT", "PGV", "VPB", "NKG", "DBC", "NVL", "HCD", "CEO", "HVT", "VDS",
    "SSI",
]

# ===== Ngưỡng signal — variant B =====
VOLUME_RATIO_MIN = 1.2
ROC10_MIN        = 3.0
MACD_HIST_MIN    = 0.0
ADX14_MIN        = 16.0

USE_MA200 = False
USE_MA50  = True

MIN_HOLD_DAYS = 3

TIMEZONE     = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND = 0.4
STATE_FILE    = "../data/live_state_core_31.json"
TELEGRAM_TITLE = "ST5 CORE-31"
DELAY_BETWEEN_TICKERS = 3 
