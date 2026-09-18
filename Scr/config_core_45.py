"""
CORE-45 config — variant B (bỏ MA200, VolR>1.2, ROC10>3, ADX>16)
Ngày chốt: 2026-09-18
Backtest: CAGR 16.06%, MaxDD -2.99%, 2699 trades / 8.2 năm
"""

CORE_45 = [
    "SCI", "CSC", "PTC", "LHC", "VFG", "PSB", "APS", "IDJ", "VIX", "MHC",
    "TMT", "KDC", "VEF", "VNP", "NKG", "SHS", "KDM", "NVB", "HCM", "LGL",
    "TCO", "VDS", "TMB", "VPB", "ABB", "PGV", "HCD", "VLG", "HLD", "CEO",
    "MFS", "MVC", "PSD", "TTN", "HVT", "ITA", "SDT", "SGP", "VIB", "SFI",
    "DBC", "TVD", "CMS", "NVL", "MSB",
]

# ===== Ngưỡng signal — variant B =====
VOLUME_RATIO_MIN = 1.2
ROC10_MIN        = 3.0
MACD_HIST_MIN    = 0.0
ADX14_MIN        = 16.0

# MA filter
USE_MA200 = False   # variant B: bỏ MA200
USE_MA50  = True    # vẫn giữ MA50

# ===== Trade rules =====
MIN_HOLD_DAYS = 3

# ===== Runtime =====
TIMEZONE     = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND = 0.4   # %/vòng (buy+sell)
STATE_FILE    = "../data/live_state_core_45.json"
TELEGRAM_TITLE = "ST5 CORE-45"
DELAY_BETWEEN_TICKERS = 3   # giây 
