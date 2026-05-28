import ccxt
import pandas as pd
import numpy as np
import datetime

PAIR = "BTC/USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 12

SL_PCT = 0.008   # BTC daha volatil → daha dar SL
RR = 1.6
FUTURE_BARS = 12

exchange = ccxt.binance({
    "enableRateLimit": True
})


# -------------------------
# DATA
# -------------------------
def fetch_data(symbol, timeframe):
    now = exchange.milliseconds()
    since = now - MONTHS_BACK * 30 * 24 * 60 * 60 * 1000

    candles = []

    while since < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not batch:
            break

        candles.extend(batch)
        since = batch[-1][0] + 60 * 60 * 1000

    df = pd.DataFrame(candles, columns=["ts","o","h","l","c","v"])
    df.drop_duplicates(subset=["ts"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# -------------------------
# LIQUIDITY LEVELS
# -------------------------
def get_levels(df, lookback=20):
    return (
        df["h"].rolling(lookback).max(),
        df["l"].rolling(lookback).min()
    )


# -------------------------
# BTC TREND FILTER (IMPORTANT)
# -------------------------
def trend_filter(df):
    ma50 = df["c"].rolling(50).mean()
    ma200 = df["c"].rolling(200).mean()

    if len(df) < 200:
        return None

    if ma50.iloc[-1] > ma200.iloc[-1]:
        return "UP"
    else:
        return "DOWN"


# -------------------------
# SIGNAL ENGINE
# -------------------------
def signal(df):
    if len(df) < 200:
        return None

    highs, lows = get_levels(df)

    i = len(df) - 1

    h = df["h"].iloc[i]
    l = df["l"].iloc[i]
    c = df["c"].iloc[i]
    o = df["o"].iloc[i]

    liquidity_high = highs.iloc[i-1]
    liquidity_low = lows.iloc[i-1]

    # -------------------------
    # SWEEP (BTC ADAPTED)
    # -------------------------
    sweep_high = h > liquidity_high and c < liquidity_high
    sweep_low = l < liquidity_low and c > liquidity_low

    # -------------------------
    # DISPLACEMENT (LESS STRICT)
    # -------------------------
    body = abs(c - o)
    candle_range = h - l

    displacement = candle_range > 0 and (body / candle_range) > 0.5

    # -------------------------
    # TREND FILTER (BTC KEY EDGE)
    # -------------------------
    trend = trend_filter(df)

    # -------------------------
    # FINAL LOGIC
    # -------------------------
    if trend == "UP" and sweep_low and displacement:
        return "LONG"

    if trend == "DOWN" and sweep_high and displacement:
        return "SHORT"

    return None


# -------------------------
# BACKTEST
# -------------------------
def backtest(df):
    trades = []

    for i in range(200, len(df) - FUTURE_BARS):

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
                if row["l"] >= tp:
                    result = True
                    break
                if row["h"] <= sl:
                    break

        trades.append(result)

    return trades


# -------------------------
# RUN
# -------------------------
print("===== BTC V7 PRO REPORT =====")
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
