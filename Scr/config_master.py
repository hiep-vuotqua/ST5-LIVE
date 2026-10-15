"""
ST5 MASTER v2 — sau khi lọc thanh khoản
Cập nhật: 2026-10-15
Filter: loại 25 mã có GTGD 200 phiên < ngưỡng an toàn (xem FILTER_NOTE)
Cron: 9:45 / 10:30 / 11:15 / 13:30 / 14:00 / 14:20 VN
"""

# ============================================================
# FILTER NOTE (đọc trước khi sửa)
# Ngày filter: 2026-10-15
# Ngưỡng: GTGD trung bình 200 phiên gần nhất
# Lý do: mã GTGD thấp → mua 100tr khó khớp 1 phiên, bán càng khó
#         (khớp muộn → lỡ MH exit → thua lỗ không kiểm soát)
# Refresh: nên chạy lại filter mỗi 6 tháng, so sánh list bỏ
# 25 mã đã loại: CIG CTP FDC HLD HVT ICG KDM LGL MCG MFS MVC
#                NAG PMG PSB SAS SAV SCI SEA SLS TA9 TDH TMT VFG
#                VLG VNA
# ============================================================

RULES = {
    "CORE-28": dict(
        # Bỏ 16 mã: PMG VFG CTP MFS TMT PSB SCI SEA TDH VLG LGL HVT KDM MVC HLD ICG
        tickers=["GEX","ABB","APS","SGP","TCO","IDJ","VDS","HCM","BVS","NKG","NVL","KDC"],
        volr=1.2, roc=3.0, macd=0.0, adx=16.0, ma200=False, ma50=True, mh=3,
    ),
    "CORE-30": dict(
        # Bỏ 2 mã: VNA LGL
        tickers=["ABB","HCM","NKG","IDJ","NVL","SSI","CTS","CTR","FRT","NHA"],
        volr=1.2, roc=3.0, macd=0.0, adx=20.0, ma200=False, ma50=True, mh=5,
    ),
    "CORE-DGW": dict(
        # Bỏ 6 mã: TA9 NAG MCG SCI CTP HLD
        tickers=["VGI","SCL","CSV","LPB","VTP","SJS","DCM","DPM","BCM","TVS","DGW","APG","VPB"],
        volr=0.8, roc=1.5, macd=-0.5, adx=25.0, ma200=False, ma50=False, mh=7,
    ),
    "CORE-MBB": dict(
        # Bỏ 2 mã: SCI CTP
        tickers=["SSI","FRT","MWG","IMP","DVP","BSR","APG"],
        volr=1.0, roc=1.0, macd=-0.5, adx=15.0, ma200=True, ma50=False, mh=7,
    ),
    "CORE-TCH": dict(
        # Bỏ 11 mã: FDC CIG SAV SLS SAS SCI CTP HLD LGL PSB TMT
        tickers=["NHA","FRT","ABB","SCL","MBS","APG","SJS","HAH","SIP","CTR","MCH",
                 "STB","BCM","HTN","GEG","VPB","VDS","APS","TCO"],
        volr=1.2, roc=2.0, macd=0.0, adx=18.0, ma200=False, ma50=False, mh=10,
    ),
    "CORE-SCAN-DCM": dict(
        # Không bỏ mã nào
        tickers=["CTS","DGW","HSL","CII","CEO","MCH","DPM","VPB","FRT","BSR","VDS"],
        volr=1.5, roc=4.0, macd=0.0, adx=19.0, ma200=True, ma50=True, mh=3,
    ),
    "CORE-SCAN-GVR": dict(
        # Bỏ 1 mã: CTP
        tickers=["FRT","CEO","DGW","VPB","VIX","LPB","VCG","DPR","GVR","BFC","OIL"],
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
