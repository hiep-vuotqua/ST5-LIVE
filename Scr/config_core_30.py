"""
CORE-30 config — T3 variant ADX20/MH5
Ngày chốt: 2026-09-21
Pool: 12 mã T3 (đã lọc 2/3 năm dương 2024-2026)
Variant: khác CORE-28 (ADX20/MH5 vs ADX16/MH3) → không trùng tín hiệu
Backtest: CAGR 15.04%, MaxDD -5.74%, Ratio 2.62
Yearly: 2024 +10.27%, 2025 +11.80%, 2026 +4.35%
"""

CORE_30 = [
    "ABB", "HCM", "NKG", "IDJ", "NVL", "SSI",
    "CTS", "CTR", "FRT", "NHA", "VNA", "LGL",
]

# ===== Ngưỡng signal =====
VOLUME_RATIO_MIN = 1.2
ROC10_MIN        = 3.0
MACD_HIST_MIN    = 0.0
ADX14_MIN        = 20.0      # ← cao hơn CORE-28 (16)
USE_MA200        = False
USE_MA50         = True
MIN_HOLD_DAYS    = 5         # ← dài hơn CORE-28 (3)

# ===== Runtime =====
TIMEZONE              = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND         = 0.4
STATE_FILE            = "../data/live_state_core_30.json"
TELEGRAM_TITLE        = "ST5 CORE-30"
DELAY_BETWEEN_TICKERS = 3
