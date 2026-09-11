import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from vnstock import Quote

SUPER_CORE = [
    "NVL", "BSI", "HSG", "HDG", "CEO", "CTG", "DPM", "VCB", "FTS", "DCM",
    "SHB", "PVD", "SHS", "VCI", "NKG", "HCM", "VND", "SSI", "VIB", "VIC",
    "FRT", "VPB", "LPB", "DIG", "DXG", "MBB", "GEX", "TCH", "HPG", "PVS", "TCB", "PDR"
]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Chưa cấu hình Telegram Token/Chat ID.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def scan_market():
    signals = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for ticker in SUPER_CORE:
        try:
            q = Quote(source="VCI", symbol=ticker)
            df = q.history(start="2025-01-01", end=today_str, interval="1D")
            if df is None or len(df) < 50:
                continue
                
            df.columns = [c.capitalize() for c in df.columns]
            
            # Tính chỉ báo
            df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Vol_SMA20']
            df['ROC10'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
            
            ema12 = df['Close'].ewm(span=12, adjust=False).mean()
            ema26 = df['Close'].ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            df['MACD_Hist'] = macd - macd.ewm(span=9, adjust=False).mean()
            
            high, low, close = df['High'], df['Low'], df['Close']
            tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
            atr14 = tr.rolling(14).mean()
            up_move = high - high.shift(1)
            down_move = low.shift(1) - low
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr14)
            minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr14)
            dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
            df['ADX14'] = dx.rolling(14).mean()
            
            # Kiểm tra phiên hôm nay
            last_row = df.iloc[-1]
            is_signal = (
                (last_row['Volume_Ratio'] >= 1.2) and 
                (last_row['ROC10'] >= 2.0) and 
                (last_row['MACD_Hist'] >= -0.2) and 
                (last_row['ADX14'] >= 20.0)
            )
            
            if is_signal:
                signals.append({
                    'ticker': ticker,
                    'price': last_row['Close'],
                    'roc10': round(last_row['ROC10'], 2),
                    'vol_ratio': round(last_row['Volume_Ratio'], 2)
                })
        except Exception:
            continue

    signals = sorted(signals, key=lambda x: x['roc10'], reverse=True)
    
    if signals:
        msg = f"🚀 *TÍN HIỆU MUA BOT V1 ({today_str})*\n"
        msg += f"Tổng số mã đạt chuẩn: {len(signals)}\n\n"
        for i, s in enumerate(signals, 1):
            msg += f"{i}. *{s['ticker']}* - Giá: {s['price']:,.0f} | ROC10: +{s['roc10']}% | Vol: x{s['vol_ratio']}\n"
        msg += "\n⚠️ *Lưu ý:* Ưu tiên chọn tối đa 5 vị thế từ trên xuống dưới."
    else:
        msg = f"📊 *BÁO CÁO PHIÊN {today_str}*\nHệ thống không phát hiện tín hiệu MUA đạt chuẩn trên 32 mã SUPER CORE."
        
    send_telegram(msg)

if __name__ == "__main__":
    scan_market()
 
