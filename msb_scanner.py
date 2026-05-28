import ccxt
import pandas as pd
import numpy as np

PAIR = "BTC/USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 12

SL_PCT = 0.008
RR = 1.8
FUTURE_BARS = 12

LOOKBACK = 20

exchange = ccxt.okx({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
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
# TREND (HTF BIAS)
# -------------------------
def trend(df):
    if len(df) < 200:
        return None

    ma50 = df["c"].rolling(50).mean()
    ma200 = df["c"].rolling(200).mean()

    return "UP" if ma50.iloc[-1] > ma200.iloc[-1] else "DOWN"


# -------------------------
# SWING LEVELS (STRUCTURE)
# -------------------------
def structure_levels(df):
    highs = df["h"].rolling(LOOKBACK).max()
    lows = df["l"].rolling(LOOKBACK).min()
    return highs, lows


# -------------------------
# SIGNAL ENGINE (CONTINUATION)
# -------------------------
def signal(df):
    if len(df) < 200:
        return None

    tr = trend(df)
    highs, lows = structure_levels(df)

    i = len(df) - 1

    h = df["h"].iloc[i]
    l = df["l"].iloc[i]
    c = df["c"].iloc[i]

    last_high = highs.iloc[i-1]
    last_low = lows.iloc[i-1]

    # -------------------------
    # BOS (BREAK OF STRUCTURE)
    # -------------------------
    bos_up = c > last_high
    bos_down = c < last_low

    # -------------------------
    # RETEST LOGIC (ENTRY EDGE)
    # -------------------------
    retest_high = (l <= last_high) and (c > last_high)
    retest_low = (h >= last_low) and (c < last_low)

    # -------------------------
    # FINAL LOGIC
    # -------------------------
    if tr == "UP" and bos_up and retest_high:
        return "LONG"

    if tr == "DOWN" and bos_down and retest_low:
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
print("===== BTC V8 CONTINUATION ENGINE =====")

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

        print(
            f"{PAIR} | Trades:{len(results)} "
            f"| Win:{wins} Loss:{losses} "
            f"| WR:{wr}%"
        )
