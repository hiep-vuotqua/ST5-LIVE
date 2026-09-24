# -*- coding: utf-8 -*-
"""Fetch KBS + tính indicators cho CORE-VGCD."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vnstock.api.quote import Quote

TZ = "Asia/Ho_Chi_Minh"


def rma(s, n):
    return s.ewm(alpha=1/n, adjust=False).mean()


def adx_wilder(df, n=14):
    h, l, c = df['high'], df['low'], df['close']
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    up = h.diff(); dn = -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr = rma(tr, n)
    pdi = 100 * rma(pdm, n) / atr
    mdi = 100 * rma(mdm, n) / atr
    dx  = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return rma(dx, n), pdi, mdi


def fetch_and_indicators(symbol, days=500):
    """Fetch từ 2019 (warm-up ADX) → tính indicators → trả df."""
    today = datetime.now().strftime("%Y-%m-%d")
    start = "2019-01-01"
    q = Quote(symbol=symbol, source="KBS")
    df = q.history(start=start, end=today, interval="1D")
    if df is None or len(df) == 0:
        return None
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)

    # Volume MA20
    df['vol_ma'] = df['volume'].rolling(20).mean()

    # ROC10
    df['roc'] = df['close'].pct_change(10) * 100

    # MACD hist
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    sig   = macd.ewm(span=9, adjust=False).mean()
    df['hist'] = macd - sig

    # MA50, MA200
    df['ma50']  = df['close'].rolling(50).mean()
    df['ma200'] = df['close'].rolling(200).mean()

    # ADX Wilder 14
    adx, pdi, mdi = adx_wilder(df)
    df['adx'] = adx
    df['pdi'] = pdi
    df['mdi'] = mdi

    return df.tail(days).reset_index(drop=True) 
