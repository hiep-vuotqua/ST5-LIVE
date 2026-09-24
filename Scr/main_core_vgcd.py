# -*- coding: utf-8 -*-
"""CORE-VGCD — multi-variant live bot. Chạy: cd Scr && python main_core_vgcd.py"""

import os
import json
import time
import requests
from datetime import datetime
import pytz

from config_core_vgcd import (
    POOL_CONFIG, STATE_FILE, TELEGRAM_TITLE,
    TIMEZONE, FEE_PER_ROUND, DELAY_BETWEEN_TICKERS
)
from data_core_vgcd import fetch_and_indicators

TZ = pytz.timezone(TIMEZONE)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("[TG] no token/chat, skip")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"[TG] fail: {e}")


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def entry_signal(row, cfg):
    """Check tín hiệu vào lệnh cho 1 dòng df."""
    if row['volume'] <= row['vol_ma'] * cfg['volR']:
        return False
    if row['roc'] <= cfg['roc']:
        return False
    if row['hist'] <= cfg['macd_hist']:
        return False
    if row['adx'] <= cfg['adx_min']:
        return False
    if row['pdi'] <= row['mdi']:
        return False
    if cfg.get('use_ma200') and row['close'] <= row['ma200']:
        return False
    if cfg.get('use_ma50') and row['close'] <= row['ma50']:
        return False
    return True


def main():
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    print(f"=== CORE-VGCD run @ {now.strftime('%Y-%m-%d %H:%M %Z')} ===")

    state = load_state()
    entries, exits, errors = [], [], []

    for tk, cfg in POOL_CONFIG.items():
        try:
            df = fetch_and_indicators(tk, days=500)
            if df is None or len(df) < 200:
                errors.append(f"{tk}: no data")
                continue

            last = df.iloc[-1]
            tkr_state = state.setdefault(tk, {
                "in_position": False, "entry_price": None,
                "entry_date": None, "entry_i": None, "bars_held": 0
            })

            # --- Nếu đang giữ ---
            if tkr_state["in_position"]:
                tkr_state["bars_held"] = tkr_state.get("bars_held", 0) + 1
                hold = tkr_state["bars_held"]
                mh = cfg["mh"]
                if hold >= mh:
                    exit_price = float(last['close'])
                    entry_price = float(tkr_state["entry_price"])
                    ret = (exit_price / entry_price - 1) - FEE_PER_ROUND
                    exits.append({
                        "tk": tk, "entry": entry_price, "exit": exit_price,
                        "ret": ret, "hold": hold
                    })
                    tkr_state["in_position"] = False
                    tkr_state["entry_price"] = None
                    tkr_state["entry_date"] = None
                    tkr_state["bars_held"] = 0
                continue  # đang giữ → không check entry mới

            # --- Nếu chưa giữ → check entry ---
            if entry_signal(last, cfg):
                tkr_state["in_position"] = True
                tkr_state["entry_price"] = float(last['close'])
                tkr_state["entry_date"] = str(last['time'].date())
                tkr_state["bars_held"] = 0
                entries.append({
                    "tk": tk, "price": float(last['close']),
                    "date": str(last['time'].date()),
                    "adx": float(last['adx']), "roc": float(last['roc']),
                    "cfg": f"ADX{cfg['adx_min']}/MH{cfg['mh']}/ROC{cfg['roc']}"
                })

        except BaseException as e:
            errors.append(f"{tk}: {str(e)[:80]}")
        time.sleep(DELAY_BETWEEN_TICKERS)

    save_state(state)

    # --- Telegram ---
    lines = [f"<b>{TELEGRAM_TITLE}</b> — {now.strftime('%d/%m %H:%M')}"]
    if entries:
        lines.append(f"\n🟢 <b>ENTRY ({len(entries)})</b>")
        for e in entries:
            lines.append(f"  • {e['tk']}: {e['price']:.2f} | ADX={e['adx']:.1f} ROC={e['roc']:.1f} | {e['cfg']}")
    if exits:
        lines.append(f"\n🔴 <b>EXIT ({len(exits)})</b>")
        for x in exits:
            emo = "✅" if x['ret'] > 0 else "❌"
            lines.append(f"  {emo} {x['tk']}: {x['entry']:.2f} → {x['exit']:.2f} | {x['ret']*100:+.2f}% | hold={x['hold']}")
    if not entries and not exits:
        lines.append("\n(không có tín hiệu)")
    if errors:
        lines.append(f"\n⚠️ errors: {len(errors)}")
        for e in errors[:5]:
            lines.append(f"  {e}")

    send_telegram("\n".join(lines))
    print(f"Entries: {len(entries)} | Exits: {len(exits)} | Errors: {len(errors)}")


if __name__ == "__main__":
    main() 
