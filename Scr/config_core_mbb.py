# Scr/config_core_mbb.py
# Cấu hình riêng cho CORE-MBB LIVE

CORE_MBB = [
    # RealEstate
    "QCG", "KDC", "CEO", "D2D", "HUT",
    # Securities
    "ORS", "TVB", "MBS", "SSI", "TCI",
    # Retail
    "TIP", "MCH", "FRT", "MWG",
    # Construction
    "CTR", "VGS", "KSB", "TLH",
    # Pharma
    "IMP", "AGP", "DBD",
    # Transport
    "VEA", "VTO", "HVN",
    # Bank
    "CTG", "HDB", "MSB",
    # Industrial
    "DVP", "TTN",
    # Agriculture
    "BFC", "ANV",
    # Oil
    "BSR", "PGS",
    # Other
    "HAH",
    # Tech
    "ONE",
]

# =========================
# ST5 V1.4-MBB — FROZEN
# =========================

VOLUME_RATIO_MIN = 1.0
ROC10_MIN = 1.0
MACD_HIST_MIN = -0.5
ADX14_MIN = 15.0

# =========================
# MIN HOLD — 10 PHIÊN DAILY
# =========================

MIN_HOLD_DAYS = 10

# =========================
# GIỜ GIAO DỊCH VIỆT NAM
# =========================

MORNING_START = "09:15"
MORNING_END = "11:30"

AFTERNOON_START = "13:00"
AFTERNOON_END = "14:30"

TIMEZONE = "Asia/Ho_Chi_Minh"
