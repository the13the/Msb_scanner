import ccxt
import pandas as pd
import numpy as np

PAIR = "BTC/USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 12

INITIAL_BALANCE = 10000
RISK_PER_TRADE = 0.01  # %1 risk
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
# SIGNAL
# -------------------------
def signal(df):
    if len(df) < 200:
        return None

    tr = trend(df)
    highs, lows = levels(df)

    i = len(df) - 1

    h = df["h"].iloc[i]
    l = df["l"].iloc[i]
    c = df["c"].iloc[i]

    last_high = highs.iloc[i-1]
    last_low = lows.iloc[i-1]

    bos_up = c > last_high
    bos_down = c < last_low

    retest_high = l <= last_high and c > last_high
    retest_low = h >= last_low and c < last_low

    if tr == "UP" and bos_up and retest_high:
        return "LONG"

    if tr == "DOWN" and bos_down and retest_low:
        return "SHORT"

    return None


# -------------------------
# PROP FIRM BACKTEST ENGINE
# -------------------------
def backtest(df):
    balance = INITIAL_BALANCE
    equity_curve = [balance]

    max_balance = balance
    max_drawdown = 0

    trades = 0
    wins = 0
    losses = 0

    for i in range(200, len(df) - FUTURE_BARS):

        sub = df.iloc[:i]
        side = signal(sub)

        if not side:
            continue

        entry = df["o"].iloc[i+1]

        risk_amount = balance * RISK_PER_TRADE
        sl_distance = entry * SL_PCT

        position_size = risk_amount / sl_distance

        if side == "LONG":
            sl = entry - sl_distance
            tp = entry + sl_distance * RR
        else:
            sl = entry + sl_distance
            tp = entry - sl_distance * RR

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
                if row["l"] <= tp:
                    result = "WIN"
                    break
                if row["h"] >= sl:
                    result = "LOSS"
                    break

        if result == "WIN":
            pnl = risk_amount * RR
            balance += pnl
            wins += 1

        elif result == "LOSS":
            pnl = -risk_amount
            balance += pnl
            losses += 1

        else:
            continue

        trades += 1
        equity_curve.append(balance)

        max_balance = max(max_balance, balance)
        drawdown = (max_balance - balance) / max_balance
        max_drawdown = max(max_drawdown, drawdown)

    return trades, wins, losses, balance, max_drawdown, equity_curve


# -------------------------
# RUN
# -------------------------
print("===== BTC PROP FIRM ENGINE =====")

df = fetch_data(PAIR, TIMEFRAME)

if df.empty:
    print("NO DATA")

else:
    trades, wins, losses, final_balance, mdd, curve = backtest(df)

    if trades == 0:
        print("NO SIGNAL")

    else:
        wr = round(wins / trades * 100, 2)
        profit = round(final_balance - INITIAL_BALANCE, 2)

        print(f"Trades: {trades}")
        print(f"Win: {wins} Loss: {losses}")
        print(f"WR: {wr}%")
        print(f"Final Balance: {final_balance}$")
        print(f"Profit: {profit}$")
        print(f"Max Drawdown: {round(mdd*100,2)}%")
