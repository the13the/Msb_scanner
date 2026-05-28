import ccxt
import pandas as pd
import numpy as np

# ==========================
# CONFIG
# ==========================
TIMEFRAMES = {
    "15m": 17280,   # yaklaşık 6 ay
    "1h": 4320      # yaklaşık 6 ay
}

PIVOT = 5
OB_LOOKBACK = 20

SL_PCT = 0.01
RR = 1.2

PAIR = "BTC/USDT:USDT"

ex = ccxt.okx({
    "enableRateLimit": True,
    "options": {"defaultType": "swap"}
})


# ==========================
# DATA
# ==========================
def fetch(symbol, tf, limit):
    try:
        data = ex.fetch_ohlcv(symbol, tf, limit=limit)

        df = pd.DataFrame(
            data,
            columns=["ts", "o", "h", "l", "c", "v"]
        )

        return df

    except Exception as e:
        print("fetch error:", symbol, tf, e)
        return pd.DataFrame()


# ==========================
# SWINGS
# ==========================
def swings(df):
    h = df["h"].values
    l = df["l"].values

    sh = []
    sl = []

    for i in range(PIVOT, len(df) - PIVOT):

        if h[i] == np.max(h[i - PIVOT:i + PIVOT + 1]):
            sh.append((i, h[i]))

        if l[i] == np.min(l[i - PIVOT:i + PIVOT + 1]):
            sl.append((i, l[i]))

    return sh, sl


# ==========================
# CHOCH
# ==========================
def choch(sh, sl):

    if len(sh) < 2 or len(sl) < 2:
        return None

    if sh[-1][1] < sh[-2][1]:
        return "DOWN"

    if sl[-1][1] > sl[-2][1]:
        return "UP"

    return None


# ==========================
# LIQUIDITY
# ==========================
def liquidity(close, sh, sl):

    if len(sh) < 2 or len(sl) < 2:
        return False, False

    sweep_high = close >= max([x[1] for x in sh[-2:]])
    sweep_low = close <= min([x[1] for x in sl[-2:]])

    return sweep_high, sweep_low


# ==========================
# ORDER BLOCK
# ==========================
def order_block(df, idx):

    start = max(0, idx - OB_LOOKBACK)

    for i in range(idx, start, -1):

        rng = df["h"].iloc[i] - df["l"].iloc[i]
        body = abs(df["c"].iloc[i] - df["o"].iloc[i])

        if rng == 0:
            continue

        if body / rng > 0.55:

            return (
                df["h"].iloc[i],
                df["l"].iloc[i]
            )

    return None


# ==========================
# SIGNAL
# ==========================
def signal(sub):

    sh, sl = swings(sub)

    if len(sh) < 2 or len(sl) < 2:
        return None

    trend = choch(sh, sl)

    if trend is None:
        return None

    close = sub["c"].iloc[-1]

    sweep_high, sweep_low = liquidity(close, sh, sl)

    ob = order_block(sub, len(sub) - 2)

    if ob is None:
        return None

    ob_high, ob_low = ob

    risk = close * SL_PCT
    reward = abs(ob_high - close)

    rr = reward / risk if risk > 0 else 0

    if rr < RR:
        return None

    if trend == "UP" and sweep_low:
        return "LONG"

    if trend == "DOWN" and sweep_high:
        return "SHORT"

    return None


# ==========================
# BACKTEST
# ==========================
def backtest(df):

    trades = []

    for i in range(80, len(df) - 24):

        sub = df.iloc[:i]

        side = signal(sub)

        if side is None:
            continue

        entry = sub["c"].iloc[-1]

        if side == "LONG":
            tp = entry * (1 + SL_PCT * RR)
            sl = entry * (1 - SL_PCT)

        else:
            tp = entry * (1 - SL_PCT * RR)
            sl = entry * (1 + SL_PCT)

        future = df.iloc[i:i + 24]

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


# ==========================
# RUN
# ==========================
def run():

    print("===== DYDX 6 MONTH REPORT =====")

    for tf, limit in TIMEFRAMES.items():

        print(f"\n===== {tf.upper()} =====")

        df = fetch(PAIR, tf, limit)

        if df.empty:
            print("DATA YOK")
            continue

        results = backtest(df)

        if len(results) == 0:
            print("NO SIGNAL")
            continue

        wins = sum(results)
        losses = len(results) - wins
        wr = round((wins / len(results)) * 100, 2)

        print(PAIR)
        print("Trades:", len(results))
        print("Win:", wins)
        print("Loss:", losses)
        print("Winrate:", wr, "%")


if __name__ == "__main__":
    run()
