# ============================================================
# CORE-MSRA MAIN — Signal + Telegram + Update state
# ============================================================
import json
import os
from datetime import datetime
import pandas as pd
import requests

from config_core_msra import (
    TICKERS, ADX14_MIN, MIN_HOLD_DAYS, FEE_ROUND,
    TELEGRAM_TOKEN_ENV, TELEGRAM_CHAT_ID_ENV, STATE_FILE,
)
from data_core_msra import load_stock, add_indicators, add_signal


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"positions": {}, "last_run": None, "history": []}
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state["last_run"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def send_telegram(msg):
    token = os.environ.get(TELEGRAM_TOKEN_ENV)
    chat_id = os.environ.get(TELEGRAM_CHAT_ID_ENV)
    if not token or not chat_id:
        print("⚠️ Thiếu TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id, "text": msg,
            "parse_mode": "HTML", "disable_web_page_preview": True,
        }, timeout=15)
        return r.ok
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def run():
    state = load_state()
    positions = state.get("positions", {})
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"=== CORE-MSRA RUN — {today} ===")
    print(f"Số mã: {len(TICKERS)} | Đang giữ: {len(positions)} vị thế\n")

    signals_buy = []
    signals_sell = []
    errors = []

    for ticker in TICKERS:
        try:
            df = load_stock(ticker)
            if df is None or len(df) < 200:
                errors.append((ticker, "no data"))
                continue
            df = add_indicators(df)
            df = add_signal(df, adx_min=ADX14_MIN)
            last = df.iloc[-1]
            last_date = pd.to_datetime(last["Date"]).strftime("%Y-%m-%d")
            signal_on = bool(last["Signal"])
            close = float(last["Close"])
            src = df.attrs.get("source", "?")

            # Xử lý position
            if ticker in positions:
                pos = positions[ticker]
                buy_date = pd.to_datetime(pos["buy_date"])
                hold_days = (pd.to_datetime(last["Date"]) - buy_date).days

                if (not signal_on) and hold_days >= MIN_HOLD_DAYS:
                    # BÁN
                    buy_price = pos["buy_price"]
                    ret = (close / buy_price - 1) * 100 - FEE_ROUND
                    signals_sell.append({
                        "ticker": ticker,
                        "buy_date": pos["buy_date"],
                        "sell_date": last_date,
                        "buy_price": buy_price,
                        "sell_price": close,
                        "hold_days": hold_days,
                        "ret_net": ret,
                    })
                    state["history"].append({
                        "ticker": ticker,
                        "action": "SELL",
                        "date": last_date,
                        "price": close,
                        "ret_net": round(ret, 2),
                    })
                    del positions[ticker]
                else:
                    # Giữ
                    print(f"  {ticker:<6} HOLD ({hold_days}d) close={close:.2f} src={src}")

            else:
                if signal_on:
                    # MUA
                    signals_buy.append({
                        "ticker": ticker,
                        "date": last_date,
                        "price": close,
                    })
                    positions[ticker] = {
                        "buy_date": last_date,
                        "buy_price": close,
                        "entry_signal": "A1i+50",
                    }
                    state["history"].append({
                        "ticker": ticker,
                        "action": "BUY",
                        "date": last_date,
                        "price": close,
                    })
                else:
                    print(f"  {ticker:<6} no signal close={close:.2f} src={src}")

        except Exception as e:
            errors.append((ticker, str(e)[:60]))
            print(f"  {ticker:<6} ERROR: {str(e)[:60]}")

    state["positions"] = positions
    save_state(state)

    # --- Telegram ---
    msg_lines = [f"<b>📊 CORE-MSRA — {today}</b>", ""]

    if signals_buy:
        msg_lines.append(f"<b>🟢 MUA ({len(signals_buy)}):</b>")
        for s in signals_buy:
            msg_lines.append(f"  • <b>{s['ticker']}</b> @ {s['price']:.2f}")
        msg_lines.append("")

    if signals_sell:
        msg_lines.append(f"<b>🔴 BÁN ({len(signals_sell)}):</b>")
        for s in signals_sell:
            emoji = "✅" if s["ret_net"] > 0 else "❌"
            msg_lines.append(
                f"  • <b>{s['ticker']}</b> @ {s['sell_price']:.2f} "
                f"({s['hold_days']}d, {emoji} {s['ret_net']:+.2f}%)"
            )
        msg_lines.append("")

    if not signals_buy and not signals_sell:
        msg_lines.append("<i>Không có tín hiệu mới.</i>")
        msg_lines.append("")

    msg_lines.append(f"<i>Đang giữ: {len(positions)}/{len(TICKERS)}</i>")
    if errors:
        msg_lines.append(f"<i>⚠️ Lỗi: {len(errors)} mã</i>")

    msg = "\n".join(msg_lines)
    print("\n" + msg)
    send_telegram(msg)

    print(f"\n✅ Done. {len(signals_buy)} MUA, {len(signals_sell)} BÁN.")


if __name__ == "__main__":
    run()
