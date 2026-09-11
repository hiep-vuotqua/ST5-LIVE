# Scr/config_core_tch.py
# Cấu hình CORE-TCH — 34 mã
# Version: V1.4-CORE-TCH Final
# Áp dụng: 11/09/2026

# ===== DANH SÁCH 34 MÃ =====
CORE_TCH = [
    "NHA", "FRT", "FDC", "CIG", "QCG", "SAV", "VIX", "ABB", "SCL",
    "MBS", "APG", "SJS", "SLS", "SAS", "HAH", "SIP", "CTR", "MCH",
    "IMP", "PCE", "STB", "BCM", "ANV", "NTP", "DBD", "MSB", "HTN",
    "TMS", "GEG", "POW", "AST", "TCM", "VSC", "HTI",
]

# ===== NGƯỠNG CHIẾN LƯỢC =====
VOLUME_RATIO_MIN = 1.2
ROC10_MIN        = 2.0
MACD_HIST_MIN    = 0.0
ADX14_MIN        = 15.0

# ===== MIN HOLD =====
MIN_HOLD_DAYS = 10  # phiên

# ===== GIỜ GIAO DỊCH =====
MORNING_START   = "09:15"
MORNING_END     = "11:30"
AFTERNOON_START = "13:00"
AFTERNOON_END   = "14:30"
TIMEZONE        = "Asia/Ho_Chi_Minh"

# ===== PHÍ + THUẾ =====
FEE_PER_ROUND = 0.4  # % mỗi vòng

# ===== STATE FILE =====
STATE_FILE = "data/live_state_core_tch.json"

# ===== TELEGRAM =====
TELEGRAM_TITLE = "ST5 CORE-TCH"

# ===== DELAY GIỮA CÁC MÃ =====
DELAY_BETWEEN_TICKERS = 3  # giây
