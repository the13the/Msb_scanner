import ccxt
import pandas as pd
import numpy as np

PAIR = "DYDX/USDT:USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 3
LIMIT = 500

PIVOT = 6
ATR_LEN = 14

SL_ATR_MULT = 1.2
RR = 2.0

CONFIRM_BARS = 3

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

    all_candles = []
    tf_ms = 60 * 60 * 1000

    while since < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=LIMIT)
        if not batch:
            break
        all_candles.extend(batch)
        since = batch[-1][0] + tf_ms

    df = pd.DataFrame(all_candles, columns=["ts","o","h","l","c","v"])
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
# SWING POINTS
# =========================
def swings(df):
    highs = df["h"].values
    lows = df["l"].values

    sh = []
    sl = []

    for i in range(PIVOT, len(df) - PIVOT):
        if highs[i] == np.max(highs[i-PIVOT:i+PIVOT+1]):
            sh.append((i, highs[i]))
        if lows[i] == np.min(lows[i-PIVOT:i+PIVOT+1]):
            sl.append((i, lows[i]))

    return sh, sl


# =========================
# FVG DETECTION (simple 3-candle imbalance)
# =========================
def find_fvg(df, i):
    if i < 2:
        return None

    c1 = df.iloc[i-2]
    c3 = df.iloc[i]

    # bullish FVG
    if c1["h"] < c3["l"]:
        return ("bull", c1["h"], c3["l"])

    # bearish FVG
    if c1["l"] > c3["h"]:
        return ("bear", c3["h"], c1["l"])

    return None


# =========================
# MSS CHECK
# =========================
def mss_bull(df, last_swing_high):
    return df["c"].iloc[-1] > last_swing_high

def mss_bear(df, last_swing_low):
    return df["c"].iloc[-1] < last_swing_low


# =========================
# SIGNAL ENGINE
# =========================
def signal(df):
    if len(df) < 120:
        return None

    sh, sl = swings(df)

    if len(sh) < 3 or len(sl) < 3:
        return None

    last_sh = sh[-1][1]
    last_sl = sl[-1][1]

    price = df["c"].iloc[-1]

    # LIQUIDITY SWEEP (wick based)
    sweep_low = df["l"].iloc[-1] < last_sl
    sweep_high = df["h"].iloc[-1] > last_sh

    # MSS confirmation
    bull_mss = mss_bull(df, last_sh)
    bear_mss = mss_bear(df, last_sl)

    # FVG
    fvg = find_fvg(df, len(df)-1)

    if sweep_low and bull_mss and fvg and fvg[0] == "bull":
        return "LONG"

    if sweep_high and bear_mss and fvg and fvg[0] == "bear":
        return "SHORT"

    return None


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
        side = signal(sub)

        if side is None:
            i += 1
            continue

        atr_val = sub["atr"].iloc[-1]
        if np.isnan(atr_val):
            i += 1
            continue

        # WAIT CONFIRMATION (important V3 logic)
        entry_idx = i + CONFIRM_BARS
        if entry_idx >= len(df):
            break

        entry = df["o"].iloc[entry_idx]

        sl_dist = atr_val * SL_ATR_MULT

        if side == "LONG":
            sl = entry - sl_dist
            tp = entry + sl_dist * RR
        else:
            sl = entry + sl_dist
            tp = entry - sl_dist * RR

        future = df.iloc[entry_idx:entry_idx+future_bars]

        result = None

        for _, row in future.iterrows():

            if side == "LONG":
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

        i += CONFIRM_BARS + 1

    return trades, curve


# =========================
# RUN
# =========================
print("===== DYDX V3 INSTITUTIONAL REPORT =====")

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

    final = curve[-1]
    print(f"Trades:{len(trades)} | Win:{wins} Loss:{losses} | WR:{wr}%")
    print(f"Final Equity: {round(final,3)}")
