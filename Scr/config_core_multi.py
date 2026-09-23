# ST5 CORE-MULTI — pilot 2026-09-23
# Mỗi mã có config riêng (khác variant)

POOL_CONFIG = {
    "HAH": dict(volR=1.2, roc=0.0, macd=-0.5, adx=14, ma200=True,  ma50=False, mh=5),
    "ORS": dict(volR=0.6, roc=0.0, macd=-0.5, adx=12, ma200=True,  ma50=False, mh=7),
    "VPB": dict(volR=0.8, roc=0.0, macd=-0.5, adx=14, ma200=False, ma50=True,  mh=7),
    "PVP": dict(volR=0.6, roc=0.0, macd=-0.5, adx=14, ma200=True,  ma50=False, mh=7),
    "HTN": dict(volR=0.6, roc=0.0, macd=-0.5, adx=12, ma200=True,  ma50=False, mh=10),
    "DXS": dict(volR=0.8, roc=0.0, macd=-0.5, adx=16, ma200=False, ma50=True,  mh=10),
    "FRT": dict(volR=0.6, roc=1.0, macd= 0.0, adx=14, ma200=True,  ma50=False, mh=10),
}

FEE_PER_ROUND = 0.004
TIMEZONE = "Asia/Ho_Chi_Minh"

STATE_FILE     = "../data/live_state_core_multi.json"
TELEGRAM_TITLE = "ST5 CORE-MULTI"
DELAY_BETWEEN_TICKERS = 3 
