import ccxt
import pandas as pd
import numpy as np
import requests
import os
import json
import hashlib
from datetime import datetime

# =========================
# CONFIG
# =========================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["CHAT_ID"]

CANDLE_COUNT = 300
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
]


# =========================
# STATE
# =========================
def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# =========================
# TELEGRAM
# =========================
def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


# =========================
# DATA
# =========================
def fetch(exchange, symbol, tf):
    df = pd.DataFrame(
        exchange.fetch_ohlcv(symbol, tf, limit=CANDLE_COUNT),
        columns=["t","o","h","l","c","v"]
    )
    return df


# =========================
# SWING ENGINE (REAL PIVOTS)
# =========================
def swings(df):
    highs = df["h"].values
    lows  = df["l"].values

    swing_highs = []
    swing_lows  = []

    for i in range(PIVOT_LEN, len(df)-PIVOT_LEN):
        if highs[i] == max(highs[i-PIVOT_LEN:i+PIVOT_LEN]):
            swing_highs.append((i, highs[i]))
        if lows[i] == min(lows[i-PIVOT_LEN:i+PIVOT_LEN]):
            swing_lows.append((i, lows[i]))

    return swing_highs, swing_lows


# =========================
# LIQUIDITY SWEEP
# =========================
def liquidity_sweep(df, swing_highs, swing_lows):
    price = df["c"].iloc[-1]

    swept_high = any(price > h for _, h in swing_highs[-3:])
    swept_low  = any(price < l for _, l in swing_lows[-3:])

    return swept_high, swept_low


# =========================
# STRUCTURE (BOS / CHOCH)
# =========================
def structure(df, swing_highs, swing_lows):
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None

    last_high = swing_highs[-1][1]
    prev_high = swing_highs[-2][1]

    last_low = swing_lows[-1][1]
    prev_low = swing_lows[-2][1]

    close = df["c"].iloc[-1]

    # BOS bullish
    if close > last_high:
        return "BOS_UP"

    # BOS bearish
    if close < last_low:
        return "BOS_DOWN"

    # CHoCH simple proxy
    if last_high < prev_high and close < last_low:
        return "CHOCH_DOWN"

    if last_low > prev_low and close > last_high:
        return "CHOCH_UP"

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
def signal_engine(df, swings_high, swings_low):
    sweep_high, sweep_low = liquidity_sweep(df, swings_high, swings_low)
    struct = structure(df, swings_high, swings_low)
    ob = order_block(df)

    if ob is None or struct is None:
        return None

    ob_high, ob_low = ob
    price = df["c"].iloc[-1]

    intersect = (min(ob_high, price), max(ob_low, price))

    if intersect[0] <= intersect[1]:
        return None

    if struct in ["BOS_UP", "CHOCH_UP"] and sweep_low:
        return "LONG", intersect

    if struct in ["BOS_DOWN", "CHOCH_DOWN"] and sweep_high:
        return "SHORT", intersect

    return None


# =========================
# MAIN
# =========================
def run():
    ex = ccxt.okx({"options": {"defaultType": "swap"}})

    state = load_state()

    while True:
        for tf in TIMEFRAMES:
            for pair in PAIRS:

                df = fetch(ex, pair, TIMEFRAMES[tf])

                sh, sl = swings(df)

                res = signal_engine(df, sh, sl)

                if res is None:
                    continue

                direction, zone = res

                key = f"{pair}_{tf}_{direction}_{zone[0]:.5f}_{zone[1]:.5f}"

                if key in state:
                    continue

                state[key] = True

                msg = f"""
{'🟢 LONG' if direction=='LONG' else '🔴 SHORT'}

Coin: {pair}
TF: {tf}
Zone: {zone[1]:.5f} - {zone[0]:.5f}
Time: {datetime.utcnow()}
"""

                send(msg)

                print("SENT:", key)

        save_state(state)


if __name__ == "__main__":
    run()
