# ============================================================
# ST5-LIVE — CORE-DGW-18
# Variant DGW
# Backtest: CAGR 19.70%, MaxDD -6.36%, ratio 3.10
# Yearly: 2024 +29.77%, 2025 +20.05%, 2026 +10.16%
# Ngày chốt: 2026-09-21
# ============================================================

CORE_DGW = [
    # DGW gốc (đã loại 5 mã DD cao: C69, SHS, SSI, BSR, GVR)
    "VGI", "TA9", "SCL", "CSV", "LPB",
    "VTP", "NAG", "SJS", "DCM", "DPM",
    "BCM", "TVS", "DGW", "MCG",
    # 5 mã mới (tuyển 2 tầng)
    "SCI", "CTP", "APG", "VPB", "HLD",
    # Đã loại: VHC, VND (2026 âm), APS (overfit), TVD (rủi ro)
]

# ===== DGW FROZEN RULE =====
VOLUME_RATIO_MIN = 0.8
ROC10_MIN        = 1.5
MACD_HIST_MIN    = -0.5
ADX14_MIN        = 25
MIN_HOLD_DAYS    = 7

# VNINDEX filter
VNI_MA_PERIOD = 20

# ===== TIMEZONE =====
TIMEZONE = "Asia/Ho_Chi_Minh"

# ===== STATE — FIX PATH =====
STATE_FILE = "../data/live_state_core_dgw.json"

# ===== TELEGRAM =====
TELEGRAM_TITLE = "ST5 CORE-DGW"

# ===== COST =====
FEE_PER_ROUND = 0.40
DELAY_BETWEEN_TICKERS = 3.5
