import ccxt
import pandas as pd
import numpy as np
import os
from datetime import datetime

# =========================
# CONFIG
# =========================
TIMEFRAME = "1h"
DAYS_BACK = 7
CANDLES = DAYS_BACK * 24

TP_RR = 2.0      # 1R risk → 2R reward
SL_PCT = 0.01    # %1 risk

PIVOT_LEN = 5
OB_LOOKBACK = 25

PAIRS = [
    "BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT",
    "XRP/USDT:USDT","ADA/USDT:USDT","AVAX/USDT:USDT"
]

ex = ccxt.okx({"options": {"defaultType": "swap"}})

# =========================
# DATA
# =========================
def fetch(symbol):
    try:
        df = ex.fetch_ohlcv(symbol, TIMEFRAME, limit=CANDLES)
        return pd.DataFrame(df, columns=["t","o","h","l","c","v"])
    except:
        return pd.DataFrame()

# =========================
# SWINGS (LIQUIDITY LEVELS)
# =========================
def swings(df):
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
# LIQUIDITY SWEEP (V3 CORE)
# =========================
def liquidity_sweep(df, sh, sl):
    if len(sh) < 3 or len(sl) < 3:
        return False, False

    price = df["c"].iloc[-1]

    sweep_high = price > np.max(sh[-3:])
    sweep_low  = price < np.min(sl[-3:])

    return sweep_high, sweep_low

# =========================
# CHOCH (TREND SHIFT)
# =========================
def choch(sh, sl, close):
    if len(sh) < 2 or len(sl) < 2:
        return None

    if close > sh[-2] and close < sh[-1]:
        return "DOWN_SHIFT"

    if close < sl[-2] and close > sl[-1]:
        return "UP_SHIFT"

    return None

# =========================
# ORDER BLOCK (IMPROVED)
# =========================
def order_block(df, i):
    start = max(0, i - OB_LOOKBACK)

    for j in range(i-1, start, -1):
        body = abs(df["c"].iloc[j] - df["o"].iloc[j])

        # impulse sonrası candle seçimi (daha kaliteli OB)
        if body > (df["h"].iloc[j] - df["l"].iloc[j]) * 0.6:
            return (df["h"].iloc[j], df["l"].iloc[j])

    return None

# =========================
# RR FILTER
# =========================
def rr_check(entry, ob):
    ob_h, ob_l = ob

    risk = entry * SL_PCT
    reward = abs(entry - ob_h)

    rr = reward / risk if risk != 0 else 0

    return rr >= TP_RR

# =========================
# SIGNAL ENGINE (V3)
# =========================
def signal(df):
    if len(df) < 100:
        return None

    sh, sl = swings(df)
    sweep_high, sweep_low = liquidity_sweep(df, sh, sl)
    trend = choch(sh, sl, df["c"].iloc[-1])
    ob = order_block(df, len(df)-1)

    if not ob or not trend:
        return None

    entry = df["c"].iloc[-1]

    if not rr_check(entry, ob):
        return None

    ob_h, ob_l = ob

    top = min(ob_h, entry)
    bot = max(ob_l, entry)

    if top <= bot:
        return None

    # LONG
    if trend == "UP_SHIFT" and sweep_low:
        return "LONG", (top, bot)

    # SHORT
    if trend == "DOWN_SHIFT" and sweep_high:
        return "SHORT", (top, bot)

    return None

# =========================
# BACKTEST
# =========================
def backtest(df):
    trades = []

    for i in range(100, len(df)-24):

        sub = df.iloc[:i]

        res = signal(sub)
        if not res:
            continue

        direction, zone = res
        entry = sub["c"].iloc[-1]

        tp = entry * (1 + TP_RR * SL_PCT) if direction == "LONG" else entry * (1 - TP_RR * SL_PCT)
        sl = entry * (1 - SL_PCT) if direction == "LONG" else entry * (1 + SL_PCT)

        future = df.iloc[i:i+24]

        win = False

        for _, r in future.iterrows():

            if direction == "LONG":
                if r["h"] >= tp:
                    win = True
                    break
                if r["l"] <= sl:
                    break

            else:
                if r["l"] <= tp:
                    win = True
                    break
                if r["h"] >= sl:
                    break

        trades.append(win)

    return trades

# =========================
# RUN REPORT
# =========================
def run():
    print("===== V3 PERFORMANCE REPORT =====")

    total_trades = 0
    wins = 0

    for pair in PAIRS:

        df = fetch(pair)
        if df.empty:
            continue

        results = backtest(df)

        if not results:
            print(pair, "NO SIGNAL")
            continue

        w = sum(results)
        l = len(results) - w

        winrate = (w / len(results)) * 100

        print(f"\n{pair}")
        print("Trades:", len(results))
        print("Win:", w, "Loss:", l)
        print("Winrate:", round(winrate, 2), "%")

        total_trades += len(results)
        wins += w

    overall = (wins / total_trades) * 100 if total_trades > 0 else 0

    print("\n===== SUMMARY =====")
    print("Total Trades:", total_trades)
    print("Winrate:", round(overall, 2), "%")

if __name__ == "__main__":
    run()
