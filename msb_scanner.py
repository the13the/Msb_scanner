import ccxt
import pandas as pd
import numpy as np
import time
PAIRS = [
"BTC/USDT",
"ETH/USDT",
"DYDX/USDT"
]
TIMEFRAMES = {
"15m": 15 * 60 * 1000,
"1h": 60 * 60 * 1000
}
MONTHS_BACK = 6
PIVOT = 5
OB_LOOKBACK = 20
SL_PCT = 0.01
RR = 1.2
BATCH_LIMIT = 100
exchange = ccxt.okx({
"enableRateLimit": True,
"options": {
"defaultType": "swap"
}
})
def fetch_real_history(symbol, tf):
now_ms = exchange.milliseconds()
months_ms = MONTHS_BACK * 30 * 24 * 60 * 60 * 1000
since = now_ms - months_ms
all_data = []

while since < now_ms:
    try:
        batch = exchange.fetch_ohlcv(
            symbol,
            timeframe=tf,
            since=since,
            limit=BATCH_LIMIT
        )

        if not batch:
            break

        all_data.extend(batch)

        last_ts = batch[-1][0]

        if last_ts <= since:
            break

        since = last_ts + TIMEFRAMES[tf]

        time.sleep(exchange.rateLimit / 1000)

    except Exception as e:
        print("fetch error:", symbol, tf, e)
        break

if not all_data:
    return pd.DataFrame()

df = pd.DataFrame(
    all_data,
    columns=["ts", "o", "h", "l", "c", "v"]
)

df = df.drop_duplicates(subset=["ts"])
df = df.reset_index(drop=True)

return df
def swings(df):
highs = df["h"].values
lows = df["l"].values
swing_highs = []
swing_lows = []

for i in range(PIVOT, len(df) - PIVOT):

    if highs[i] == np.max(highs[i - PIVOT:i + PIVOT + 1]):
        swing_highs.append((i, highs[i]))

    if lows[i] == np.min(lows[i - PIVOT:i + PIVOT + 1]):
        swing_lows.append((i, lows[i]))

return swing_highs, swing_lows
def choch(swing_highs, swing_lows):
if len(swing_highs) < 2 or len(swing_lows) < 2:
    return None

if swing_highs[-1][1] < swing_highs[-2][1]:
    return "DOWN"

if swing_lows[-1][1] > swing_lows[-2][1]:
    return "UP"

return None
def liquidity(close, swing_highs, swing_lows):
if len(swing_highs) < 2 or len(swing_lows) < 2:
    return False, False

sweep_high = close >= max(x[1] for x in swing_highs[-2:])
sweep_low = close <= min(x[1] for x in swing_lows[-2:])

return sweep_high, sweep_low
def order_block(df, idx):
start = max(0, idx - OB_LOOKBACK)

for i in range(idx, start, -1):

    candle_range = df["h"].iloc[i] - df["l"].iloc[i]
    body = abs(df["c"].iloc[i] - df["o"].iloc[i])

    if candle_range == 0:
        continue

    if body / candle_range > 0.55:
        return (
            df["h"].iloc[i],
            df["l"].iloc[i]
        )

return None
def signal(sub):
swing_highs, swing_lows = swings(sub)

if len(swing_highs) < 2 or len(swing_lows) < 2:
    return None

trend = choch(swing_highs, swing_lows)

if trend is None:
    return None

close = sub["c"].iloc[-1]

sweep_high, sweep_low = liquidity(
    close,
    swing_highs,
    swing_lows
)

ob = order_block(sub, len(sub) - 2)

if ob is None:
    return None

ob_high, _ = ob

risk = close * SL_PCT
reward = abs(ob_high - close)

rr_value = reward / risk if risk > 0 else 0

if rr_value < RR:
    return None

if trend == "UP" and sweep_low:
    return "LONG"

if trend == "DOWN" and sweep_high:
    return "SHORT"

return None
def backtest(df, tf):
trades = []

future_bars = 24 if tf == "15m" else 12

for i in range(80, len(df) - future_bars):

    sub = df.iloc[:i]

    side = signal(sub)

    if side is None:
        continue

    entry = sub["c"].iloc[-1]

    if side == "LONG":
        tp = entry * (1 + (SL_PCT * RR))
        sl = entry * (1 - SL_PCT)
    else:
        tp = entry * (1 - (SL_PCT * RR))
        sl = entry * (1 + SL_PCT)

    future = df.iloc[i:i + future_bars]

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
def run():
print("===== REAL 6 MONTH PERFORMANCE REPORT =====")

for tf in TIMEFRAMES:

    print(f"\n===== {tf.upper()} =====")

    for pair in PAIRS:

        print(f"Loading {pair} {tf}...")

        df = fetch_real_history(pair, tf)

        if df.empty:
            print(pair, "NO DATA")
            continue

        print("Candles:", len(df))

        results = backtest(df, tf)

        if len(results) == 0:
            print(pair, "NO SIGNAL")
            continue

        wins = sum(results)
        losses = len(results) - wins
        wr = round((wins / len(results)) * 100, 2)

        print(
            f"{pair} | Trades:{len(results)} "
            f"| Win:{wins} Loss:{losses} "
            f"| WR:{wr}%"
        )
if name == "main":
run()
