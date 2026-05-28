import ccxt
import pandas as pd
import numpy as np

PAIR = "BTC/USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 12

INITIAL_BALANCE = 10000
RISK_PER_TRADE = 0.01

SL_PCT = 0.008
RR = 1.8
FUTURE_BARS = 12

LOOKBACK = 20
ATR_PERIOD = 14
COOLDOWN = 5  # candles

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
# ATR (VOLATILITY FILTER)
# -------------------------
def atr(df, period=14):
    high_low = df["h"] - df["l"]
    high_close = np.abs(df["h"] - df["c"].shift())
    low_close = np.abs(df["l"] - df["c"].shift())

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# -------------------------
# TREND
# -------------------------
def trend(df):
    ma50 = df["c"].rolling(50).mean()
    ma200 = df["c"].rolling(200).mean()
    return "UP" if ma50.iloc[-1] > ma200.iloc[-1] else "DOWN"


# -------------------------
# STRUCTURE
# -------------------------
def levels(df):
    highs = df["h"].rolling(LOOKBACK).max()
    lows = df["l"].rolling(LOOKBACK).min()
    return highs, lows


# -------------------------
# SIGNAL (OPTIMIZED)
# -------------------------
def signal(df, i):
    if i < 200:
        return None

    tr = trend(df.iloc[:i])
    highs, lows = levels(df.iloc[:i])

    h = df["h"].iloc[i]
    l = df["l"].iloc[i]
    c = df["c"].iloc[i]
    o = df["o"].iloc[i]

    # ATR FILTER
    if df["atr"].iloc[i] < df["atr"].mean():
        return None

    last_high = highs.iloc[i-1]
    last_low = lows.iloc[i-1]

    bos_up = c > last_high
    bos_down = c < last_low

    retest_high = l <= last_high and c > last_high
    retest_low = h >= last_low and c < last_low

    # momentum candle
    body = abs(c - o)
    rng = h - l
    strong = rng > 0 and body / rng > 0.6

    if tr == "UP" and bos_up and retest_high and strong:
        return "LONG"

    if tr == "DOWN" and bos_down and retest_low and strong:
        return "SHORT"

    return None


# -------------------------
# BACKTEST (WITH COOLDOWN + RISK CONTROL)
# -------------------------
def backtest(df):
    df["atr"] = atr(df, ATR_PERIOD)

    balance = INITIAL_BALANCE
    equity = [balance]

    last_trade_index = -COOLDOWN

    trades = 0
    wins = 0
    losses = 0
    max_dd = 0
    peak = balance

    for i in range(200, len(df) - FUTURE_BARS):

        if i - last_trade_index < COOLDOWN:
            continue

        side = signal(df, i)

        if not side:
            continue

        entry = df["o"].iloc[i+1]

        risk = balance * RISK_PER_TRADE
        sl_dist = entry * SL_PCT

        if side == "LONG":
            sl = entry - sl_dist
            tp = entry + sl_dist * RR
        else:
            sl = entry + sl_dist
            tp = entry - sl_dist * RR

        future = df.iloc[i+1:i+1+FUTURE_BARS]

        result = None

        for _, row in future.iterrows():

            if side == "LONG":
                if row["h"] >= tp:
                    result = "WIN"
                    break
                if row["l"] <= sl:
                    result = "LOSS"
                    break
            else:
                if row["l"] >= tp:
                    result = "WIN"
                    break
                if row["h"] >= sl:
                    result = "LOSS"
                    break

        if result is None:
            continue

        last_trade_index = i
        trades += 1

        if result == "WIN":
            balance += risk * RR
            wins += 1
        else:
            balance -= risk
            losses += 1

        equity.append(balance)

        peak = max(peak, balance)
        dd = (peak - balance) / peak
        max_dd = max(max_dd, dd)

    return trades, wins, losses, balance, max_dd


# -------------------------
# RUN
# -------------------------
print("===== BTC PROP FIRM V9 OPTIMIZED =====")

df = fetch_data(PAIR, TIMEFRAME)

if df.empty:
    print("NO DATA")
else:
    trades, wins, losses, bal, dd = backtest(df)

    if trades == 0:
        print("NO SIGNAL")
    else:
        wr = round(wins / trades * 100, 2)
        profit = round(bal - INITIAL_BALANCE, 2)

        print(f"Trades: {trades}")
        print(f"Win: {wins} Loss: {losses}")
        print(f"WR: {wr}%")
        print(f"Final Balance: {bal}$")
        print(f"Profit: {profit}$")
        print(f"Max Drawdown: {round(dd*100,2)}%")
