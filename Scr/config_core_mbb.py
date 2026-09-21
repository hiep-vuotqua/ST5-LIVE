"""
CORE-MBB config — variant A (MA200 filter)
Ngày chốt: 2026-09-21
Pool: 9 mã (T6+3) — SSI,FRT,MWG,IMP,DVP,BSR + SCI,CTP,APG
Variant: VolR1.0 / ROC1.0 / MACD-0.5 / ADX15 / MH7 / MA200 filter
Backtest: CAGR 20.41%, MaxDD -6.11%, Ratio 3.34
Yearly: 2024 +20.45%, 2025 +7.83%, 2026 +10.42%
"""

CORE_MBB = [
    # T6 (core từ MBB gốc)
    "SSI", "FRT", "MWG", "IMP", "DVP", "BSR",
    # 3 mã mở rộng (từ pool 64)
    "SCI", "CTP", "APG",
]

# ===== Signal =====
VOLUME_RATIO_MIN = 1.0
ROC10_MIN        = 1.0
MACD_HIST_MIN    = -0.5
ADX14_MIN        = 15.0
MIN_HOLD_DAYS    = 7

# ===== MA200 filter =====
USE_MA200 = True   # ← thêm
USE_MA50  = False  # hoặc True — user quyết

# ===== Runtime =====
MORNING_START = "09:15"
MORNING_END   = "11:30"
AFTERNOON_START = "13:00"
AFTERNOON_END   = "14:40"

TIMEZONE              = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND         = 0.4
STATE_FILE            = "../data/live_state_core_mbb.json"
TELEGRAM_TITLE        = "ST5 CORE-MBB"
DELAY_BETWEEN_TICKERS = 3
