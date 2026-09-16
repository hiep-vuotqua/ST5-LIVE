# ============================================================
# ST5-LIVE — CORE-DGW
# FINAL 20
# Daily 1D
# ============================================================

CORE_DGW = [
    "SHS", "BSR", "MCG", "SSI", "VHC",
    "VGI", "TA9", "SCL", "CSV", "C69",
    "LPB", "VND", "VTP", "NAG", "SJS",
    "DCM", "DPM", "BCM", "TVS", "GVR",
]

# ===== DGW FROZEN RULE =====
VOLUME_RATIO_MIN = 0.8
ROC10_MIN = 1.5
MACD_HIST_MIN = -0.5
ADX14_MIN = 25

# Minimum holding period
MIN_HOLD_DAYS = 7

# VNINDEX filter
VNI_MA_PERIOD = 20

# ===== TIMEZONE =====
TIMEZONE = "Asia/Ho_Chi_Minh"

# ===== STATE =====
STATE_FILE = "data/live_state_core_dgw.json"

# ===== TELEGRAM =====
TELEGRAM_TITLE = "ST5 CORE-DGW"

# ===== COST =====
# Buy 0.15% + sell 0.15% + tax 0.10%
FEE_PER_ROUND = 0.40

# KBS free-tier rate limit
DELAY_BETWEEN_TICKERS = 3.5

# ===== DAILY WORKFLOW =====
# CORE-DGW chạy sau khi có dữ liệu daily.
# GitHub Actions: 14:45 VN và 15:15 VN.
MORNING_START = "09:00"
MORNING_END = "11:30"

AFTERNOON_START = "13:00"
AFTERNOON_END = "15:30" 
