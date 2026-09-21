"""
CORE-28 config — Variant B, filter yearly 2/3
Ngày chốt: 2026-09-21
Backtest: CAGR 17.23%, MaxDD -4.23%, ratio 4.07, 7/7 năm lời
Filter: yearly 2024/2025/2026 dương >= 2/3 năm
ADX verify: MFS 32.57 (TV khop 100%), VDS 26.23 (TV khop 100%)
"""

CORE_28 = [
    "PMG",
    "VFG",
    "GEX",
    "ABB",
    "CTP",
    "MFS",
    "TMT",
    "APS",
    "PSB",
    "SCI",
    "SEA",
    "TDH",
    "VLG",
    "LGL",
    "HVT",
    "SGP",
    "TCO",
    "KDM",
    "MVC",
    "HLD",
    "ICG",
    "IDJ",
    "VDS",
    "HCM",
    "BVS",
    "NKG",
    "NVL",
    "KDC",
]

# ===== Ngưỡng signal (Variant B) =====
VOLUME_RATIO_MIN = 1.2
ROC10_MIN        = 3.0
MACD_HIST_MIN    = 0.0
ADX14_MIN        = 16.0
USE_MA200        = False
USE_MA50         = True
MIN_HOLD_DAYS    = 3

# ===== Runtime =====
TIMEZONE              = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND         = 0.4
STATE_FILE            = "../data/live_state_core_28.json"
TELEGRAM_TITLE        = "ST5 CORE-28"
DELAY_BETWEEN_TICKERS = 3 
