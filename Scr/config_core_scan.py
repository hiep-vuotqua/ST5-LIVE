"""
CORE-SCAN config — basket 2 luật (DCM + GVR)
Ngày chốt: 2026-10-03
DCM: 11 mã — CAGR 15.17% (full 8y) / 11.35% (4y), MaxDD -2.28%
GVR: 12 mã — CAGR 12.78% (full 8y) / 9.81% (4y), MaxDD -3.45%
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

TIMEZONE              = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND         = 0.4
STATE_FILE            = "../data/live_state_core_scan.json"
TELEGRAM_TITLE        = "ST5 CORE-SCAN"
DELAY_BETWEEN_TICKERS = 3
