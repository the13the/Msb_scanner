import ccxt
import pandas as pd
import numpy as np

# =========================
# CONFIG
# =========================
TIMEFRAME = "1h"
DAYS_BACK = 7
CANDLES = DAYS_BACK * 24

TP = 0.02   # +2%
SL = 0.01   # -1%

PAIRS = [
    "BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT",
    "XRP/USDT:USDT","ADA/USDT:USDT","AVAX/USDT:USDT"
]

PIVOT_LEN = 5
OB_LOOKBACK = 20

ex = ccxt.okx({"options": {"defaultType": "swap"}})

# =========================
def fetch(symbol):
    df = ex.fetch_ohlcv(symbol, TIMEFRAME, limit=CANDLES)
    return pd.DataFrame(df, columns=["t","o","h","l","c","v"])

# =========================
def swings(df):
    h = df["h"].values
    l = df["l"].values

    sh, sl = [], []

    for i in range(PIVOT_LEN, len(df)-PIVOT_LEN):
        if h[i] == np.max(h[i-PIVOT_LEN:i+PIVOT_LEN]):
            sh.append((i, h[i]))
        if l[i] == np.min(l[i-PIVOT_LEN:i+PIVOT_LEN]):
            sl.append((i, l[i]))

    return sh, sl

# =========================
def structure(sh, sl, close):
    if len(sh) < 2 or len(sl) < 2:
        return None

    if close > sh[-1][1]:
        return "BOS_UP"
    if close < sl[-1][1]:
        return "BOS_DOWN"

    return None

# =========================
def order_block(df, i):
    start = max(0, i-OB_LOOKBACK)
    for j in range(start, i):
        if df["o"].iloc[j] > df["c"].iloc[j]:
            return df["c"].iloc[j]
    return None

# =========================
def backtest(df):
    trades = []

    for i in range(50, len(df)-24):

        sub = df.iloc[:i]

        sh, sl = swings(sub)
        struct = structure(sh, sl, sub["c"].iloc[-1])
        ob = order_block(sub, i-1)

        if not struct or not ob:
            continue

        entry = sub["c"].iloc[-1]

        if struct == "BOS_UP":
            direction = "LONG"
            tp = entry * (1 + TP)
            slv = entry * (1 - SL)

        else:
            direction = "SHORT"
            tp = entry * (1 - TP)
            slv = entry * (1 + SL)

        future = df.iloc[i:i+24]

        result = "LOSS"

        for _, row in future.iterrows():

            if direction == "LONG":
                if row["h"] >= tp:
                    result = "WIN"
                    break
                if row["l"] <= slv:
                    break

            if direction == "SHORT":
                if row["l"] <= tp:
                    result = "WIN"
                    break
                if row["h"] >= slv:
                    break

        trades.append(result)

    return trades

# =========================
def run():
    print("===== 1 WEEK PERFORMANCE REPORT =====")

    total_trades = 0
    wins = 0

    for pair in PAIRS:

        try:
            df = fetch(pair)

            results = backtest(df)

            if not results:
                continue

            w = results.count("WIN")
            l = results.count("LOSS")

            total_trades += len(results)
            wins += w

            winrate = (w / len(results)) * 100

            print(f"\n{pair}")
            print("Trades:", len(results))
            print("Win:", w, "Loss:", l)
            print("Winrate:", round(winrate, 2), "%")

        except Exception as e:
            print("error:", pair, e)

    overall = (wins / total_trades) * 100 if total_trades > 0 else 0

    print("\n===== SUMMARY =====")
    print("Total Trades:", total_trades)
    print("Winrate:", round(overall, 2), "%")

if __name__ == "__main__":
    run()
