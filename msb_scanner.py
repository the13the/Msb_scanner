import ccxt
import pandas as pd
import numpy as np
import datetime

PAIR = "DYDX/USDT:USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 12

SL_PCT = 0.01
RR = 1.8
FUTURE_BARS = 12

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

    candles = []

    while since < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=500)
        if not batch:
            break

        candles.extend(batch)
        since = batch[-1][0] + 60 * 60 * 1000

    df = pd.DataFrame(candles, columns=["ts","o","h","l","c","v"])
    df.drop_duplicates(subset=["ts"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# -------------------------
# LIQUIDITY SWEEP
# -------------------------
def get_liquidity_levels(df, lookback=20):
    highs = df["h"].rolling(lookback).max()
    lows = df["l"].rolling(lookback).min()
    return highs, lows


# -------------------------
# FVG DETECTION (SIMPLE)
# -------------------------
def has_fvg(df, i):
    if i < 3:
        return False

    prev_high = df["h"].iloc[i-2]
    next_low = df["l"].iloc[i]

    return next_low > prev_high


# -------------------------
# SIGNAL ENGINE (PRO)
# -------------------------
def signal(df):
    if len(df) < 100:
        return None

    highs, lows = get_liquidity_levels(df)

    i = len(df) - 1

    h = df["h"].iloc[i]
    l = df["l"].iloc[i]
    c = df["c"].iloc[i]

    liquidity_high = highs.iloc[i-1]
    liquidity_low = lows.iloc[i-1]

    # -------------------------
    # SWEEP
    # -------------------------
    sweep_high = h > liquidity_high and c < liquidity_high
    sweep_low = l < liquidity_low and c > liquidity_low

    # -------------------------
    # DISPLACEMENT
    # -------------------------
    body = abs(c - df["o"].iloc[i])
    candle_range = h - l
    displacement = candle_range > 0 and body / candle_range > 0.6

    # -------------------------
    # FVG FILTER
    # -------------------------
    fvg = has_fvg(df, i)

    # -------------------------
    # FINAL LOGIC
    # -------------------------
    if sweep_low and displacement and fvg:
        return "LONG"

    if sweep_high and displacement and fvg:
        return "SHORT"

    return None


# -------------------------
# BACKTEST
# -------------------------
def backtest(df):
    trades = []

    for i in range(100, len(df) - FUTURE_BARS):

        sub = df.iloc[:i]
        side = signal(sub)

        if not side:
            continue

        entry = df["o"].iloc[i+1]

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
print("===== DYDX V7 PRO REBUILD =====")
df = fetch_data(PAIR, TIMEFRAME)

if df.empty:
    print("NO DATA")
else:
    results = backtest(df)

    if not results:
        print("NO SIGNAL")
    else:
        wins = sum(results)
        losses = len(results) - wins

        wr = round(wins / len(results) * 100, 2)

        print(f"{PAIR} | Trades:{len(results)} | Win:{wins} Loss:{losses} | WR:{wr}%")
