# ST5 CORE-B3 — pilot 2026-09-23
# Variant chung: VolR0.8 / ROC0.0 / MACD-0.5 / ADX12 / bỏ MA200+MA50 / MH7
# Backtest: MSB n=98 PF1.75 | HII n=125 PF1.60 | PVD n=136 PF1.44

CORE_B3 = ["MSB", "HII", "PVD"]

VOLUME_RATIO_MIN = 0.8
ROC10_MIN        = 0.0
MACD_HIST_MIN    = -0.5
ADX14_MIN        = 12

USE_MA200 = False
USE_MA50  = False

MIN_HOLD_DAYS = 7
FEE_PER_ROUND = 0.004

TIMEZONE = "Asia/Ho_Chi_Minh"

STATE_FILE     = "../data/live_state_core_b3.json"
TELEGRAM_TITLE = "ST5 CORE-B3"
DELAY_BETWEEN_TICKERS = 3 
