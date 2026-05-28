import ccxt
import pandas as pd
import numpy as np
import requests
import os
import json
import time
from datetime import datetime

# =========================
# ENV (GitHub Secrets)
# =========================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID        = os.environ.get("CHAT_ID")

# =========================
# CONFIG
# =========================
CANDLE_COUNT = 200
PIVOT_LEN = 4
OB_LOOKBACK = 15
STATE_FILE = "state.json"

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
        return set(json.load(open(STATE_FILE)))
    return set()

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(list(state), f)

# =========================
# TELEGRAM (DEBUG VERSION)
# =========================
def send(msg):
    print("\n===== TELEGRAM DEBUG =====")

    print("[DEBUG] TOKEN:", bool(TELEGRAM_TOKEN))
    print("[DEBUG] CHAT_ID:", bool(CHAT_ID))

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[ERROR] ENV missing!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": msg
    }

    try:
        r = requests.post(url, data=payload, timeout=10)

        print("[DEBUG] STATUS:", r.status_code)
        print("[DEBUG] RESPONSE:", r.text)

        if r.status_code == 200:
            print("[SUCCESS] Telegram sent")
        else:
            print("[FAIL] Telegram error")

    except Exception as e:
        print("[EXCEPTION]", str(e))

# =========================
# DATA
# =========================
def fetch(exchange, symbol, tf):
    try:
        data = exchange.fetch_ohlcv(symbol, tf, limit=CANDLE_COUNT)
        time.sleep(0.08)
        return pd.DataFrame(data, columns=["t","o","h","l","c","v"])
    except Exception as e:
        print("[FETCH ERROR]", symbol, tf, e)
        return pd.DataFrame()

# =========================
# SWING ENGINE
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
# STRUCTURE
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
    if df.empty or len(df) < 50:
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

    if struct == "BOS_UP":
        return "LONG", (top, bot)

    if struct == "BOS_DOWN":
        return "SHORT", (top, bot)

    return None

# =========================
# MAIN
# =========================
def run():
    print("===== SYSTEM START =====")

    ex = ccxt.okx({"options": {"defaultType": "swap"}})

    state = load_state()

    print("[INFO] Pairs:", len(PAIRS))

    for pair in PAIRS:
        for tf in TIMEFRAMES:

            try:
                df = fetch(ex, pair, TIMEFRAMES[tf])

                res = signal(df)
                if not res:
                    continue

                direction, zone = res

                key = f"{pair}_{tf}_{direction}_{zone[0]:.5f}_{zone[1]:.5f}"

                if key in state:
                    continue

                state.add(key)

                msg = f"""
{'🟢 LONG' if direction=='LONG' else '🔴 SHORT'}

Coin: {pair}
TF: {tf}
Zone: {zone[1]:.5f} - {zone[0]:.5f}
Time: {datetime.utcnow()}
"""

                send(msg)

                print("[SENT]", key)

                time.sleep(0.15)

            except Exception as e:
                print("[ERROR]", pair, tf, e)

    save_state(state)
    print("===== SYSTEM END =====")

if __name__ == "__main__":
    run()
