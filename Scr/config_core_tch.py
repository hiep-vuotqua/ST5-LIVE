# Scr/config_core_tch.py
# Cấu hình CORE-TCH — Phương án A
# Pool: E + 10 mã pool 64 (30 mã)
# Variant: ADX18 (thay vì ADX15 gốc)
# Ngày chốt: 2026-09-21
# Backtest: CAGR 20.49%, MaxDD -4.62%, Ratio 4.44
# Yearly: 2024 +20.70%, 2025 +17.23%, 2026 +4.13%

# ===== DANH SÁCH 30 MÃ =====
CORE_TCH = [
    # E pool gốc 20 mã
    "NHA", "FRT", "FDC", "CIG", "SAV",
    "ABB", "SCL", "MBS", "APG", "SJS",
    "SLS", "SAS", "HAH", "SIP", "CTR",
    "MCH", "STB", "BCM", "HTN", "GEG",
    # 10 mã pool 64
    "SCI", "CTP", "VPB", "HLD", "LGL",
    "VDS", "APS", "PSB", "TMT", "TCO",
]

# ===== NGƯỠNG CHIẾN LƯỢC =====
VOLUME_RATIO_MIN = 1.2
ROC10_MIN        = 2.0
MACD_HIST_MIN    = 0.0
ADX14_MIN        = 18.0      # ← ĐỔI từ 15 → 18

# ===== MIN HOLD =====
MIN_HOLD_DAYS = 10

# ===== GIỜ GIAO DỊCH =====
MORNING_START   = "09:15"
MORNING_END     = "11:30"
AFTERNOON_START = "13:00"
AFTERNOON_END   = "14:40"
TIMEZONE        = "Asia/Ho_Chi_Minh"

# ===== PHÍ + THUẾ =====
FEE_PER_ROUND = 0.4

# ===== STATE FILE =====
STATE_FILE = "../data/live_state_core_tch.json"

# ===== TELEGRAM =====
TELEGRAM_TITLE = "ST5 CORE-TCH"

# ===== DELAY =====
DELAY_BETWEEN_TICKERS = 3
