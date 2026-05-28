import ccxt
import pandas as pd
import numpy as np
import requests
import os
import json
import time
from datetime import datetime

# =========================
# ENV
# =========================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID        = os.environ.get("CHAT_ID")

# =========================
# CONFIG
# =========================
CANDLE_COUNT = 250
PIVOT_LEN    = 5
OB_LOOKBACK  = 20
STATE_FILE   = "state.json"

TIMEFRAMES = {
    "15m": "15m",
    "1h": "1h",
    "4h": "4h"
}

PAIRS = [
    "BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT",
    "XRP/USDT:USDT","ADA/USDT:USDT","AVAX/USDT:USDT",
    "DOGE/USDT:USDT","LINK/USDT:USDT","TON/USDT:USDT",
    "DOT/USDT:USDT","TRX/USDT:USDT","MATIC/USDT:USDT",
    "LTC/USDT:USDT","BCH/USDT:USDT","ATOM/USDT:USDT",
    "NEAR/USDT:USDT","ARB/USDT:USDT","OP/USDT:USDT",
    "INJ/USDT:USDT","APT/USDT:USDT"
]

# =========================
# STATE
# =========================
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# =========================
# TELEGRAM
# =========================
def send(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram ENV eksik")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

# =========================
# DATA
# =========================
def fetch(exchange, symbol, tf):
    try:
        data = exchange.fetch_ohlcv(symbol, tf, limit=CANDLE_COUNT)
        time.sleep(0.12)
        return pd.DataFrame(data, columns=["t","o","h","l","c","v"])
    except Exception as e:
        print("fetch error:", symbol, tf, e)
        return pd.DataFrame()

# =========================
# SWINGS
# =========================
def swings(df):
    if df.empty:
        return [], []

    h = df["h"].values
    l = df["l"].values

    sh, sl = [], []

    for i in range(PIVOT_LEN, len(df)-PIVOT_LEN):
        if h[i] == np.max(h[i-PIVOT_LEN:i+PIVOT_LEN]):
            sh.append(h[i])
        if l[i] == np.min(l[i-PIVOT_LEN:i+PIVOT_LEN]):
            sl.append(l[i])

    return sh, sl

# =========================
# STRUCTURE (BOS ONLY)
# =========================
def structure(sh, sl, close):
    if len(sh) < 2 or len(sl) < 2:
        return None

    if close > sh[-1]:
        return "BOS_UP"
    if close < sl[-1]:
        return "BOS_DOWN"

    return None

# =========================
# ORDER BLOCK
# =========================
def order_block(df):
    for i in range(len(df)-OB_LOOKBACK, len(df)):
        if df["o"].iloc[i] > df["c"].iloc[i]:
            return (df["h"].iloc[i], df["l"].iloc[i])
    return None

# =========================
# SIGNAL ENGINE
# =========================
def signal(df):
    if df.empty or len(df) < 60:
        return None

    close = df["c"].iloc[-1]

    sh, sl = swings(df)
    struct = structure(sh, sl, close)
    ob = order_block(df)

    if not struct or not ob:
        return None

    ob_h, ob_l = ob

    top = min(ob_h, close)
    bot = max(ob_l, close)

    if top <= bot:
        return None

    # noise filter (çok küçük hareketleri ele)
    strength = abs(top - bot) / close
    if strength < 0.002:
        return None

    if struct == "BOS_UP":
        return "LONG", (top, bot)

    if struct == "BOS_DOWN":
        return "SHORT", (top, bot)

    return None

# =========================
# MAIN (SINGLE RUN SAFE)
# =========================
def run():
    print("===== V2 START =====")

    ex = ccxt.okx({"options": {"defaultType": "swap"}})

    state = load_state()
    new_state = state.copy()

    total = 0

    for tf in TIMEFRAMES:
        for pair in PAIRS:

            df = fetch(ex, pair, TIMEFRAMES[tf])
            if df.empty:
                continue

            res = signal(df)
            if not res:
                continue

            direction, zone = res

            key = f"{pair}_{tf}_{direction}_{zone[0]:.5f}_{zone[1]:.5f}"

            if key in state:
                continue

            new_state[key] = True

            msg = f"""
{'🟢 LONG' if direction=='LONG' else '🔴 SHORT'}

Coin: {pair}
TF: {tf}
Zone: {zone[1]:.5f} - {zone[0]:.5f}
Time: {datetime.utcnow()}
"""

            send(msg)

            print("SENT:", key)

            total += 1

    save_state(new_state)

    print("TOTAL SIGNALS:", total)
    send(f"📊 V2 Scan tamamlandı. Sinyal: {total}")

if __name__ == "__main__":
    run()
