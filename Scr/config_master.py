"""
ST5 MASTER v3 — Tinh gọn rule + Stop Loss + Giới hạn tối đa số phiên giữ
"""

RULES = {
    "CORE-28": dict(
        tickers=["GEX","ABB","APS","SGP","TCO","IDJ","VDS","HCM","BVS","NKG","NVL","KDC"],
        volr=1.2, roc=3.0, macd=0.0, adx=16.0, ma200=False, ma50=True, mh=3,
    ),
    "CORE-30": dict(
        tickers=["ABB","HCM","NKG","IDJ","NVL","SSI","CTS","CTR","FRT","NHA"],
        volr=1.2, roc=3.0, macd=0.0, adx=20.0, ma200=False, ma50=True, mh=5,
    ),
    "CORE-DGW": dict(
        tickers=["VGI","SCL","CSV","LPB","VTP","SJS","DCM","DPM","BCM","TVS","DGW","APG","VPB"],
        volr=0.8, roc=1.5, macd=-0.5, adx=25.0, ma200=False, ma50=False, mh=7,
    ),
    "CORE-MBB": dict(
        tickers=["SSI","FRT","MWG","IMP","DVP","BSR","APG"],
        volr=1.0, roc=1.0, macd=-0.5, adx=15.0, ma200=True, ma50=False, mh=7,
    ),
    "CORE-TCH": dict(
        tickers=["NHA","FRT","ABB","SCL","MBS","APG","SJS","HAH","SIP","CTR","MCH",
                 "STB","BCM","HTN","GEG","VPB","VDS","APS","TCO"],
        volr=1.2, roc=2.0, macd=0.0, adx=18.0, ma200=False, ma50=False, mh=10,
    ),
    "CORE-SCAN-DCM": dict(
        tickers=["CTS","DGW","HSL","CII","CEO","MCH","DPM","VPB","FRT","BSR","VDS"],
        volr=1.5, roc=4.0, macd=0.0, adx=19.0, ma200=True, ma50=True, mh=3,
    ),
    # Đã bỏ CORE-SCAN-GVR vì avg ret âm (-2.17%) và giữ trung bình gần 48 phiên
}

POSITION_SIZE = 100_000_000   # 100tr/lệnh
MAX_POSITIONS = 10
CAPITAL_INITIAL = 1_000_000_000

# Chốt chặn rủi ro mới cho v3
STOP_LOSS_PCT = 8.0           # Cắt lỗ nếu giá đóng cửa giảm >= 8% so với giá vào
HARD_MAX_HOLD_DAYS = 20       # Chốt thoát cứng nếu giữ quá 20 phiên giao dịch

TIMEZONE = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND = 0.4
STATE_FILE = "../data/live_state_master_v3.json"
LOG_FILE = "../data/log_master_v3.csv"
TELEGRAM_TITLE = "ST5 MASTER v3"
DELAY_BETWEEN_TICKERS = 2
