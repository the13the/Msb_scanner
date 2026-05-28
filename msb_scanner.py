import ccxt
import pandas as pd
import numpy as np

PAIR = "DYDX/USDT:USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 3
PIVOT = 8
LIMIT = 500

SL_PCT = 0.01
RR = 1.4
FUTURE_BARS = 12

MIN_SWEEP_PCT = 0.003

exchange = ccxt.okx({
    "enableRateLimit": True,
    "options": {"defaultType": "swap"}
})


def fetch_data(symbol, timeframe):
    now = exchange.milliseconds()
    since = now - MONTHS_BACK * 30 * 24 * 60 * 60 * 1000

    tf_ms = 60 * 60 * 1000
    candles = []

    while since < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=LIMIT)
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
# SWINGS
# -------------------------
def get_swings(df):
    highs = df["h"].values
    lows = df["l"].values

    swing_highs = []
    swing_lows = []

    for i in range(PIVOT, len(df) - PIVOT):
        if highs[i] >= np.max(highs[i-PIVOT:i+PIVOT+1]):
            swing_highs.append(highs[i])

        if lows[i] <= np.min(lows[i-PIVOT:i+PIVOT+1]):
            swing_lows.append(lows[i])

    return swing_highs, swing_lows


# -------------------------
# SIGNAL ENGINE (FIXED)
# -------------------------
def signal(df):
    if len(df) < 120:
        return None

    swing_highs, swing_lows = get_swings(df)

    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return None

    last_high = swing_highs[-1]
    prev_high = swing_highs[-2]

    last_low = swing_lows[-1]
    prev_low = swing_lows[-2]

    h = df["h"].iloc[-1]
    l = df["l"].iloc[-1]
    c = df["c"].iloc[-1]

    # -------------------------
    # REAL SWEEP (FIXED)
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
    # CLEAN TREND (NO BOS, NO CONFUSION)
    # -------------------------
    trend_up = last_low > prev_low
    trend_down = last_high < prev_high

    # -------------------------
    # ENTRY LOGIC (PURE REVERSAL)
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

    for i in range(120, len(df) - FUTURE_BARS):

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
print("===== DYDX V6.1 FIXED REPORT =====")
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
