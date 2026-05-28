import ccxt
import pandas as pd
import numpy as np
import datetime

PAIR = "DYDX/USDT:USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 12

SL_PCT = 0.01
RR = 1.5
FUTURE_BARS = 12

MIN_SWEEP_PCT = 0.003

exchange = ccxt.okx({
    "enableRateLimit": True,
    "options": {"defaultType": "swap"}
})


# -------------------------
# DATA
# -------------------------
def fetch_data(symbol, timeframe):
    now = exchange.milliseconds()
    since = now - MONTHS_BACK * 30 * 24 * 60 * 60 * 1000

    tf_ms = 60 * 60 * 1000
    candles = []

    while since < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=500)
        if not batch:
            break

        candles.extend(batch)
        last = batch[-1][0]

        if last <= since:
            break

        since = last + tf_ms

    df = pd.DataFrame(candles, columns=["ts","o","h","l","c","v"])
    df.drop_duplicates(subset=["ts"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# -------------------------
# STRUCTURE (REAL SWING BASED ON FRAGMENTS)
# -------------------------
def get_structure(df):
    highs = df["h"].values
    lows = df["l"].values

    structure_highs = []
    structure_lows = []

    # daha sıkı structure detection
    for i in range(3, len(df) - 3):

        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            structure_highs.append(highs[i])

        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            structure_lows.append(lows[i])

    return structure_highs, structure_lows


# -------------------------
# SIGNAL ENGINE (V7 FIX)
# -------------------------
def signal(df):
    if len(df) < 150:
        return None

    structure_highs, structure_lows = get_structure(df)

    if len(structure_highs) < 3 or len(structure_lows) < 3:
        return None

    last_high = structure_highs[-1]
    prev_high = structure_highs[-2]

    last_low = structure_lows[-1]
    prev_low = structure_lows[-2]

    h = df["h"].iloc[-1]
    l = df["l"].iloc[-1]
    c = df["c"].iloc[-1]

    # -------------------------
    # REAL SWEEP (LIQUIDITY GRAB)
    # -------------------------
    sweep_high = (
        h > last_high and
        c < last_high and
        ((h - last_high) / last_high) > MIN_SWEEP_PCT
    )

    sweep_low = (
        l < last_low and
        c > last_low and
        ((last_low - l) / last_low) > MIN_SWEEP_PCT
    )

    # -------------------------
    # TRUE BOS (BREAK OF STRUCTURE)
    # -------------------------
    bos_up = c > last_high
    bos_down = c < last_low

    # -------------------------
    # STRUCTURE TREND
    # -------------------------
    trend_up = last_low > prev_low
    trend_down = last_high < prev_high

    # -------------------------
    # FINAL LOGIC (CLEAN VERSION)
    # -------------------------
    if trend_up and sweep_low:
        return "LONG"

    if trend_down and sweep_high:
        return "SHORT"

    return None


# -------------------------
# BACKTEST
# -------------------------
def backtest(df):
    trades = []

    for i in range(150, len(df) - FUTURE_BARS):

        sub = df.iloc[:i]
        side = signal(sub)

        if not side:
            continue

        entry = df["o"].iloc[i + 1]

        if side == "LONG":
            sl = entry * (1 - SL_PCT)
            tp = entry + (entry - sl) * RR
        else:
            sl = entry * (1 + SL_PCT)
            tp = entry - (sl - entry) * RR

        future = df.iloc[i+1:i+1+FUTURE_BARS]

        result = False

        for _, row in future.iterrows():

            if side == "LONG":
                if row["h"] >= tp:
                    result = True
                    break
                if row["l"] <= sl:
                    break
            else:
                if row["l"] <= tp:
                    result = True
                    break
                if row["h"] >= sl:
                    break

        trades.append(result)

    return trades


# -------------------------
# RUN
# -------------------------
print("===== DYDX V7 FIX REPORT =====")
print("Loading", PAIR, TIMEFRAME)

df = fetch_data(PAIR, TIMEFRAME)

if df.empty:
    print("NO DATA")

else:
    print("Candles:", len(df))

    results = backtest(df)

    if not results:
        print("NO SIGNAL")

    else:
        wins = sum(results)
        losses = len(results) - wins

        wr = round(wins / len(results) * 100, 2)

        print(
            f"{PAIR} | Trades:{len(results)} "
            f"| Win:{wins} Loss:{losses} "
            f"| WR:{wr}%"
        )
