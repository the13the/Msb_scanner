import ccxt
import pandas as pd
import numpy as np
import time

# ==========================
# CONFIG
# ==========================
TIMEFRAMES = {
    "15m": 2880,  # 30 gün
    "1h": 720
}

DAYS_FORWARD = 24
PIVOT = 5
OB_LOOKBACK = 20

SL_PCT = 0.01
RR = 1.2

PAIRS = [
    "BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT","XRP/USDT:USDT","ADA/USDT:USDT",
    "AVAX/USDT:USDT","LINK/USDT:USDT","DOT/USDT:USDT","MATIC/USDT:USDT","TRX/USDT:USDT",
    "LTC/USDT:USDT","ATOM/USDT:USDT","XLM/USDT:USDT","NEAR/USDT:USDT","APT/USDT:USDT",
    "SUI/USDT:USDT","TON/USDT:USDT","ARB/USDT:USDT","OP/USDT:USDT","DOGE/USDT:USDT",
    "SHIB/USDT:USDT","PEPE/USDT:USDT","UNI/USDT:USDT","AAVE/USDT:USDT","INJ/USDT:USDT",
    "ICP/USDT:USDT","FIL/USDT:USDT","HBAR/USDT:USDT","STX/USDT:USDT","IMX/USDT:USDT",
    "VET/USDT:USDT","RUNE/USDT:USDT","ALGO/USDT:USDT","FTM/USDT:USDT","SAND/USDT:USDT",
    "MANA/USDT:USDT","GALA/USDT:USDT","DYDX/USDT:USDT","CRV/USDT:USDT","CHZ/USDT:USDT",
    "GMT/USDT:USDT","MINA/USDT:USDT","COMP/USDT:USDT","SNX/USDT:USDT","JUP/USDT:USDT",
    "PYTH/USDT:USDT","STRK/USDT:USDT","ENS/USDT:USDT","BLUR/USDT:USDT","ORDI/USDT:USDT"
]

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
            columns=["ts","o","h","l","c","v"]
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

    for i in range(PIVOT, len(df)-PIVOT):
        if h[i] == np.max(h[i-PIVOT:i+PIVOT+1]):
            sh.append((i, h[i]))

        if l[i] == np.min(l[i-PIVOT:i+PIVOT+1]):
            sl.append((i, l[i]))

    return sh, sl


# ==========================
# V3.1 BALANCE
# ==========================
def choch(sh, sl):
    if len(sh) < 2 or len(sl) < 2:
        return None

    if sh[-1][1] < sh[-2][1]:
        return "DOWN"

    if sl[-1][1] > sl[-2][1]:
        return "UP"

    return None


def liquidity(close, sh, sl):
    if len(sh) < 2 or len(sl) < 2:
        return False, False

    sweep_high = close >= max([x[1] for x in sh[-2:]])
    sweep_low = close <= min([x[1] for x in sl[-2:]])

    return sweep_high, sweep_low


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


def signal(sub):
    sh, sl = swings(sub)

    if len(sh) < 2 or len(sl) < 2:
        return None

    trend = choch(sh, sl)

    if trend is None:
        return None

    close = sub["c"].iloc[-1]

    sweep_high, sweep_low = liquidity(close, sh, sl)

    ob = order_block(sub, len(sub)-2)

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

    for i in range(80, len(df)-DAYS_FORWARD):

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

        future = df.iloc[i:i+DAYS_FORWARD]

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

    print("===== V3.1 PERFORMANCE REPORT =====")

    for tf, limit in TIMEFRAMES.items():

        print(f"\n===== {tf.upper()} =====")

        total_trades = 0
        total_wins = 0
        best_coin = None
        best_wr = -1

        for pair in PAIRS:

            df = fetch(pair, tf, limit)

            if df.empty:
                continue

            results = backtest(df)

            if len(results) == 0:
                print(pair, "NO SIGNAL")
                continue

            wins = sum(results)
            losses = len(results) - wins
            wr = round((wins / len(results))*100, 2)

            print(
                f"{pair} | Trades:{len(results)} "
                f"| Win:{wins} Loss:{losses} "
                f"| WR:{wr}%"
            )

            total_trades += len(results)
            total_wins += wins

            if wr > best_wr:
                best_wr = wr
                best_coin = pair

            time.sleep(0.08)

        overall = (
            round((total_wins / total_trades)*100, 2)
            if total_trades > 0 else 0
        )

        print("\nSUMMARY")
        print("Trades:", total_trades)
        print("Winrate:", overall, "%")
        print("Best Coin:", best_coin)
        print("Best WR:", best_wr)


if __name__ == "__main__":
    run()
