# ============================================================
# CORE-MSRA V3 CONFIG
# TOP30 — FROZEN
# ============================================================

TICKERS = [
    "FTS", "FIT", "HU4", "DGW", "CTS",
    "EVG", "MBS", "KLB", "LPB", "C47",
    "BCE", "PDB", "BSR", "IDJ", "DCM",
    "PET", "CTR", "GVR", "HAG", "CAP",
    "NHA", "NAF", "MCH", "POS", "MBB",
    "GEX", "KSQ", "CLH", "BMP", "OIL",
]

# --- MSRA V3 ---
# GIỮ NGUYÊN LUẬT V3 FROZEN
# Các tham số dưới đây sẽ được thay đúng theo V3 research code.

VOL_RATIO_MIN = 1.5
ROC10_MIN = 4.0
MACD_HIST_MIN = 0.0
ADX14_MIN = 30

MIN_HOLD_DAYS = 3
FEE_ROUND = 0.4  # %/round

# --- Telegram ---
TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "TELEGRAM_CHAT_ID"

# --- State ---
STATE_FILE = "data/live_state_core_msra.json"

# --- Data ---
DATA_START = "2018-09-01"
