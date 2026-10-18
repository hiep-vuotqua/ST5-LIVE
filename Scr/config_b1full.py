"""
Config bot ST5-B1FULL — Merge-12 + Trail 10%.
12 mã = Merge-13 bỏ SHS (mã overfit 2025→2026, PF 15.78→0).

Backtest (2021-01 → 2026-10):
  5Y CAGR 13.90% | DD -8.48% | 3Y CAGR 15.85% | DD -6.40% | 2026 -1.92%
"""

B1FULL_RULES = {
    # ticker: dict(adx, volr, roc, macd, ma50, ma200, mh, variant, sector)
    "ACV": dict(adx=16, volr=1.2, roc=3.0, macd=None, ma50=True,  ma200=False, mh=3,  variant="V1_C28B", sector="HangKhong"),
    "ANV": dict(adx=18, volr=1.2, roc=2.0, macd=None, ma50=False, ma200=False, mh=10, variant="V5_TCH",  sector="ThuySan"),
    "CTP": dict(adx=16, volr=1.2, roc=3.0, macd=None, ma50=True,  ma200=False, mh=3,  variant="V1_C28B", sector="BDS_KCN"),
    "EVF": dict(adx=18, volr=1.2, roc=2.0, macd=None, ma50=False, ma200=False, mh=10, variant="V5_TCH",  sector="TaiChinhTD"),
    "VDS": dict(adx=20, volr=1.2, roc=3.0, macd=None, ma50=True,  ma200=False, mh=5,  variant="V2_C30",  sector="ChungKhoan"),
    "DXG": dict(adx=18, volr=1.2, roc=2.0, macd=None, ma50=False, ma200=False, mh=10, variant="V5_TCH",  sector="BDS"),
    "GMD": dict(adx=16, volr=1.2, roc=3.0, macd=None, ma50=True,  ma200=False, mh=3,  variant="V1_C28B", sector="Cang"),
    "HAH": dict(adx=18, volr=1.2, roc=2.0, macd=None, ma50=False, ma200=False, mh=10, variant="V5_TCH",  sector="Cang"),
    "LPB": dict(adx=18, volr=1.2, roc=2.0, macd=None, ma50=False, ma200=False, mh=10, variant="V5_TCH",  sector="NganHang"),
    "MBS": dict(adx=27, volr=1.2, roc=4.0, macd=None, ma50=False, ma200=False, mh=3,  variant="V7_GVR",  sector="ChungKhoan"),
    "SSI": dict(adx=18, volr=1.2, roc=2.0, macd=None, ma50=False, ma200=False, mh=10, variant="V5_TCH",  sector="ChungKhoan"),
    "TCB": dict(adx=18, volr=1.2, roc=2.0, macd=None, ma50=False, ma200=False, mh=10, variant="V5_TCH",  sector="NganHang"),
}

CAPITAL_ALLOC = dict(
    nav           = 1_000_000_000,   # 1 tỷ
    size_pct      = 0.10,            # 10% NAV/lệnh — ĐÚNG BACKTEST
    max_positions = 10,
)

# TRAIL 10% — cắt lỗ khi close <= peak * (1 - trail_pct/100)
TRAIL_PCT = 10.0

TELEGRAM_PREFIX = "ST5 B1FULL"

# ⚠️ NẾU MUỐN ĐỔI SIZE:
#   size_pct=0.15 → max_pos nên giảm còn 6 (150tr × 6 = 900tr)
#   size_pct=0.20 → max_pos nên giảm còn 5 (200tr × 5 = 1 tỷ)
#   CHƯA BACKTEST ở size >10% → chưa khuyến nghị đổi.
