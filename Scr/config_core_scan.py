"""
CORE-SCAN config — basket 2 luật (DCM + GVR) + Tier sizing
Ngày chốt: 2026-10-03
Tier A (VolR>2.5)=150tr | Tier B (1.5-2.5)=100tr | Tier C (<1.5)=60tr
Backtest 3 năm 2023-2025: CAGR 17.18%, MaxDD -4.77%, Sharpe 2.21, Calmar 3.60
Cron: 9:35 + 13:15 + 14:45 VN, T2-T6
"""

DCM_BASKET = [
    "CTS", "DGW", "HSL", "CII", "CEO", "MCH", "DPM",
    "VPB", "FRT", "BSR", "VDS",
]

GVR_BASKET = [
    "FRT", "CEO", "DGW", "VPB", "VIX", "LPB", "CTP",
    "VCG", "DPR", "GVR", "BFC", "OIL",
]

RULE_PARAMS = {
    "DCM": dict(volr=1.5, roc=4.0, macd=0.0, adx=19.0, ma200=True,  ma50=True,  hold=3),
    "GVR": dict(volr=1.2, roc=4.0, macd=0.0, adx=27.0, ma200=False, ma50=False, hold=3),
}

# Tier sizing
TIER_A_VOLR = 2.5
TIER_B_VOLR = 1.5
SIZE_A = 150_000_000
SIZE_B = 100_000_000
SIZE_C = 60_000_000

CAPITAL_INITIAL = 1_000_000_000
MAX_POSITIONS   = 10
DD_ALERT_THRESHOLD = -5.0   # Alert khi DD < -5%

TIMEZONE              = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND         = 0.4
STATE_FILE            = "../data/live_state_core_scan.json"
LOG_FILE              = "../data/log_core_scan.csv"
TELEGRAM_TITLE        = "ST5 CORE-SCAN"
DELAY_BETWEEN_TICKERS = 3
