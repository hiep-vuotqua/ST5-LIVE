"""
CORE-MSRA config — Phương án F (T6 filter)
Ngày chốt: 2026-09-21
Pool: 14 mã (T3 + dd>-35 + pf3>1.5)
Backtest: CAGR 10.32%, MaxDD -3.82%, Ratio 2.70
Yearly: 2024 +8.11%, 2025 +6.20%, 2026 +7.76%
"""

TICKERS = [
    "DGW", "CTS", "EVG", "BCE", "BSR",
    "DCM", "PET", "GVR", "HAG", "NHA",
    "POS", "GEX", "BMP", "OIL",
]

# --- MSRA V3 (giữ nguyên) ---
VOL_RATIO_MIN = 1.5
ROC10_MIN = 4.0
MACD_HIST_MIN = 0.0
ADX14_MIN = 22.0

MIN_HOLD_DAYS = 3
FEE_ROUND = 0.4

# --- Telegram ---
TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "TELEGRAM_CHAT_ID"

# --- State — FIX path ---
STATE_FILE = "../data/live_state_core_msra.json"

# --- Data ---
DATA_START = "2018-09-01"

# ===== Giờ giao dịch =====
MORNING_START   = "09:15"
MORNING_END     = "11:30"
AFTERNOON_START = "13:00"
AFTERNOON_END   = "14:40"
TIMEZONE        = "Asia/Ho_Chi_Minh"
