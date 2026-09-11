# ============================================================
# CORE-MSRA CONFIG
# 20 mã — Luật A1i+50 (ADX30)
# ============================================================

TICKERS = [
    "IDJ", "LHC", "DPM", "ITA", "CTS", "FIT", "FTS", "MHC",
    "CSV", "BFC", "HUT", "OIL", "EVG", "DDV", "HLD",
    "NHA", "HAG", "DGW", "NAG", "MSR",
]

# --- Luật A1i+50 ---
VOL_RATIO_MIN = 1.5
ROC10_MIN = 4.0
MACD_HIST_MIN = 0.0
ADX14_MIN = 30
MIN_HOLD_DAYS = 3
FEE_ROUND = 0.4  # %/round

# --- Telegram (dùng chung MBB/TCH) ---
TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "TELEGRAM_CHAT_ID"

# --- State ---
STATE_FILE = "data/live_state_core_msra.json"

# --- Data ---
DATA_START = "2018-09-01" 
