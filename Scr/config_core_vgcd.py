# -*- coding: utf-8 -*-
"""CORE-VGCD — 28 mã, multi-variant (luật VGC variant D + near-miss riêng)."""

TIMEZONE = "Asia/Ho_Chi_Minh"
FEE_PER_ROUND = 0.004
STATE_FILE = "../data/live_state_core_vgcd.json"
TELEGRAM_TITLE = "ST5 CORE-VGCD"
DELAY_BETWEEN_TICKERS = 3

# Config chung cho 18 mã pool A (VGC variant D)
_CFG_A = {
    "volR": 1.5, "roc": 2.0, "macd_hist": 0.0, "adx_min": 15,
    "use_ma200": True, "use_ma50": False, "mh": 3,
}

# Config riêng cho 10 mã near-miss
POOL_CONFIG = {
    # --- Pool A (18 mã) ---
    "CTS": _CFG_A, "CEO": _CFG_A, "FTS": _CFG_A, "GEE": _CFG_A,
    "VGC": _CFG_A, "SSI": _CFG_A, "BSI": _CFG_A, "DCM": _CFG_A,
    "MBS": _CFG_A, "HSL": _CFG_A, "HHS": _CFG_A, "BSR": _CFG_A,
    "MCH": _CFG_A, "VIC": _CFG_A, "DPM": _CFG_A, "MBB": _CFG_A,
    "ACV": _CFG_A, "DDV": _CFG_A,

    # --- Pool B (10 mã near-miss, config riêng) ---
    "DGW": {"volR": 1.5, "roc": 2.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 7},
    "C69": {"volR": 1.5, "roc": 2.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 7},
    "ELC": {"volR": 1.5, "roc": 1.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 5},
    "FRT": {"volR": 1.5, "roc": 2.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 7},
    "VDS": {"volR": 1.5, "roc": 2.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 7},
    "VIX": {"volR": 1.5, "roc": 1.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 5},
    "GAS": {"volR": 1.5, "roc": 1.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 7},
    "TNI": {"volR": 1.5, "roc": 1.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 5},
    "CTG": {"volR": 1.5, "roc": 1.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 5},
    "PLX": {"volR": 1.5, "roc": 1.0, "macd_hist": 0.0, "adx_min": 14, "use_ma200": True, "use_ma50": False, "mh": 5},
}

CORE_VGCD = list(POOL_CONFIG.keys()) 
