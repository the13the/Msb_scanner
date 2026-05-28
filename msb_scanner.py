import ccxt
import pandas as pd
import numpy as np

PAIR = "DYDX/USDT:USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 3
LIMIT = 500

PIVOT = 6
ATR_LEN = 14

SCORE_THRESHOLD = 70

SL_ATR_MULT = 1.2
RR = 2.0

FEE = 0.0004
SLIPPAGE = 0.0002

exchange = ccxt.okx({
    "enableRateLimit": True,
    "options": {"defaultType": "swap"}
})


# =========================
# DATA
# =========================
def fetch_data(symbol, timeframe):
    now = exchange.milliseconds()
    since = now - MONTHS_BACK * 30 * 24 * 60 * 60 * 1000

    data = []
    tf_ms = 60 * 60 * 1000

    while since < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=LIMIT)
        if not batch:
            break
        data.extend(batch)
        since = batch[-1][0] + tf_ms

    df = pd.DataFrame(data, columns=["ts","o","h","l","c","v"])
    df.drop_duplicates("ts", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# =========================
# ATR
# =========================
def atr(df, length=14):
    high = df["h"]
    low = df["l"]
    close = df["c"]

    tr = np.maximum(
        high - low,
        np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1)))
    )

    return tr.rolling(length).mean()


# =========================
# SWINGS
# =========================
def swings(df):
    highs = df["h"].values
    lows = df["l"].values

    sh, sl = [], []

    for i in range(PIVOT, len(df) - PIVOT):
        if highs[i] == np.max(highs[i-PIVOT:i+PIVOT+1]):
            sh.append(highs[i])
        if lows[i] == np.min(lows[i-PIVOT:i+PIVOT+1]):
            sl.append(lows[i])

    return sh, sl


# =========================
# DISPLACEMENT
# =========================
def displacement(df, i, atr_val):
    body = abs(df["c"].iloc[i] - df["o"].iloc[i])
    return body > atr_val * 1.2


# =========================
# FVG PROXIMITY
# =========================
def fvg_score(df, i):
    if i < 2:
        return 0

    c1 = df.iloc[i-2]
    c3 = df.iloc[i]

    if c1["h"] < c3["l"] or c1["l"] > c3["h"]:
        return 15

    return 0


# =========================
# SIGNAL SCORING ENGINE
# =========================
def score_signal(df):
    if len(df) < 120:
        return None, 0

    atr_val = atr(df, ATR_LEN).iloc[-1]
    if np.isnan(atr_val):
        return None, 0

    sh, sl = swings(df)
    if len(sh) < 3 or len(sl) < 3:
        return None, 0

    last_sh = sh[-1]
    last_sl = sl[-1]

    i = len(df) - 1

    score_long = 0
    score_short = 0

    # SWEEP
    if df["l"].iloc[i] < last_sl:
        score_long += 40

    if df["h"].iloc[i] > last_sh:
        score_short += 40

    # DISPLACEMENT
    if displacement(df, i, atr_val):
        score_long += 25
        score_short += 25

    # MSS (simplified but realistic)
    if df["c"].iloc[i] > last_sh:
        score_long += 20

    if df["c"].iloc[i] < last_sl:
        score_short += 20

    # FVG bonus
    score_long += fvg_score(df, i)
    score_short += fvg_score(df, i)

    if score_long >= SCORE_THRESHOLD:
        return "LONG", score_long

    if score_short >= SCORE_THRESHOLD:
        return "SHORT", score_short

    return None, 0


# =========================
# BACKTEST
# =========================
def backtest(df):
    df["atr"] = atr(df, ATR_LEN)

    trades = []
    equity = 1.0
    curve = [equity]

    future_bars = 12

    i = 120

    while i < len(df) - future_bars:

        sub = df.iloc[:i]
        sig, score = score_signal(sub)

        if sig is None:
            i += 1
            continue

        atr_val = sub["atr"].iloc[-1]
        entry_idx = i + 1

        entry = df["o"].iloc[entry_idx]

        sl_dist = atr_val * SL_ATR_MULT

        if sig == "LONG":
            sl = entry - sl_dist
            tp = entry + sl_dist * RR
        else:
            sl = entry + sl_dist
            tp = entry - sl_dist * RR

        future = df.iloc[entry_idx:entry_idx+future_bars]

        result = None

        for _, row in future.iterrows():
            if sig == "LONG":
                if row["l"] <= sl:
                    result = -1
                    break
                if row["h"] >= tp:
                    result = 1
                    break
            else:
                if row["h"] >= sl:
                    result = -1
                    break
                if row["l"] <= tp:
                    result = 1
                    break

        if result is None:
            i += 1
            continue

        r = result * (sl_dist / entry)

        r -= FEE * 2
        r -= SLIPPAGE

        equity *= (1 + r)
        curve.append(equity)

        trades.append(result > 0)

        i += 1

    return trades, curve


# =========================
# RUN
# =========================
print("===== DYDX V5 SCORING REPORT =====")

df = fetch_data(PAIR, TIMEFRAME)

if df.empty:
    print("NO DATA")
    exit()

print("Candles:", len(df))

trades, curve = backtest(df)

if not trades:
    print("NO SIGNAL")
else:
    wins = sum(trades)
    losses = len(trades) - wins

    wr = round(wins / len(trades) * 100, 2)

    print(f"Trades:{len(trades)} | Win:{wins} Loss:{losses} | WR:{wr}%")
    print(f"Final Equity: {round(curve[-1],3)}")
