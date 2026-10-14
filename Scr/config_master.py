"""
ST5 MASTER — gộp 6 bot (7 rules)
CORE-28, CORE-30, CORE-DGW, CORE-MBB, CORE-TCH, CORE-SCAN (DCM + GVR)
Cron: 9:45 / 10:30 / 11:15 / 13:30 / 14:00 / 14:20 VN
"""

RULES = {
    "CORE-28": dict(
        tickers=["PMG","VFG","GEX","ABB","CTP","MFS","TMT","APS","PSB","SCI","SEA","TDH","VLG","LGL","HVT","SGP","TCO","KDM","MVC","HLD","ICG","IDJ","VDS","HCM","BVS","NKG","NVL","KDC"],
        volr=1.2, roc=3.0, macd=0.0, adx=16.0, ma200=False, ma50=True, mh=3,
    ),
    "CORE-30": dict(
        tickers=["ABB","HCM","NKG","IDJ","NVL","SSI","CTS","CTR","FRT","NHA","VNA","LGL"],
        volr=1.2, roc=3.0, macd=0.0, adx=20.0, ma200=False, ma50=True, mh=5,
    ),
    "CORE-DGW": dict(
        tickers=["VGI","TA9","SCL","CSV","LPB","VTP","NAG","SJS","DCM","DPM","BCM","TVS","DGW","MCG","SCI","CTP","APG","VPB","HLD"],
        volr=0.8, roc=1.5, macd=-0.5, adx=25.0, ma200=False, ma50=False, mh=7,
    ),
    "CORE-MBB": dict(
        tickers=["SSI","FRT","MWG","IMP","DVP","BSR","SCI","CTP","APG"],
        volr=1.0, roc=1.0, macd=-0.5, adx=15.0, ma200=True, ma50=False, mh=7,
    ),
    "CORE-TCH": dict(
        tickers=["NHA","FRT","FDC","CIG","SAV","ABB","SCL","MBS","APG","SJS","SLS","SAS","HAH","SIP","CTR","MCH","STB","BCM","HTN","GEG","SCI","CTP","VPB","HLD","LGL","VDS","APS","PSB","TMT","TCO"],
        volr=1.2, roc=2.0, macd=0.0, adx=18.0, ma200=False, ma50=False, mh=10,
    ),
    "CORE-SCAN-DCM": dict(
        tickers=["CTS","DGW","HSL","CII","CEO","MCH","DPM","VPB","FRT","BSR","VDS"],
        volr=1.5, roc=4.0, macd=0.0, adx=19.0, ma200=True, ma50=True, mh=3,
    ),
    "CORE-SCAN-GVR": dict(
        tickers=["FRT","CEO","DGW","VPB","VIX","LPB","CTP","VCG","DPR","GVR","BFC","OIL"],
        volr=1.2, roc=4.0, macd=0.0, adx=27.0, ma200=False, ma50=False, mh=3,
    ),
}

POSITION_SIZE = 100_000_000   # 100tr/lệnh
MAX_POSITIONS = 10
CAPITAL_INITIAL = 1_000_000_000

TIMEZONE = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND = 0.4
STATE_FILE = "../data/live_state_master.json"
LOG_FILE = "../data/log_master.csv"
TELEGRAM_TITLE = "ST5 MASTER"
DELAY_BETWEEN_TICKERS = 2
