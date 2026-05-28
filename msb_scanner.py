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
RR = 2.2

DISP_ATR = 1.5

SWEEP_WINDOW = 5
DISP_WINDOW = 5
FVG_WINDOW = 5

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
# DISPLACEMENT CHECK
# =========================
def displacement(candle, atr_val):
    return abs(candle["c"] - candle["o"]) > atr_val * DISP_ATR


# =========================
# FVG DETECTION
# =========================
def detect_fvg(df, i):
    if i < 2:
        return None

    c1 = df.iloc[i-2]
    c3 = df.iloc[i]

    if c1["h"] < c3["l"]:
        return "bull"
    if c1["l"] > c3["h"]:
        return "bear"

    return None


# =========================
# STATE MACHINE
# =========================
def generate_events(df, i, atr_val, last_sh, last_sl):

    candle = df.iloc[i]

    sweep = None
    disp = False
    fvg = None

    # 1. SWEEP
    if candle["l"] < last_sl:
        sweep = "LONG"
    if candle["h"] > last_sh:
        sweep = "SHORT"

    # 2. DISPLACEMENT
    if displacement(candle, atr_val):
        disp = True

    # 3. FVG
    fvg = detect_fvg(df, i)

    return sweep, disp, fvg


# =========================
# BACKTEST
# =========================
def backtest(df):

    df["atr"] = atr(df, ATR_LEN)

    trades = []
    equity = 1.0
    curve = [equity]

    state = None
    direction = None
    setup_i = None

    future_bars = 12

    sh, sl = swings(df)

    i = 120

    while i < len(df) - future_bars:

        atr_val = df["atr"].iloc[i]
        if np.isnan(atr_val):
            i += 1
            continue

        last_sh = sh[-1]
        last_sl = sl[-1]

        candle = df.iloc[i]

        sweep, disp, fvg = generate_events(df, i, atr_val, last_sh, last_sl)

        # =========================
        # STATE 0 → WAIT SWEEP
        # =========================
        if state is None:

            if sweep == "LONG":
                state = "sweep_long"
                direction = "LONG"
                setup_i = i

            elif sweep == "SHORT":
                state = "sweep_short"
                direction = "SHORT"
                setup_i = i

            i += 1
            continue

        # =========================
        # STATE 1 → WAIT DISPLACEMENT
        # =========================
        if state in ["sweep_long", "sweep_short"]:

            if i - setup_i > SWEEP_WINDOW:
                state = None
                i += 1
                continue

            if disp:
                state = "displacement"
            i += 1
            continue

        # =========================
        # STATE 2 → WAIT FVG
        # =========================
        if state == "displacement":

            if i - setup_i > DISPLACEMENT_WINDOW:
                state = None
                i += 1
                continue

            if fvg is not None:
                state = "ready"
            i += 1
            continue

        # =========================
        # STATE 3 → ENTRY (RETRACE)
        # =========================
        if state == "ready":

            entry_idx = i + 1
            if entry_idx >= len(df):
                break

            entry = df["o"].iloc[entry_idx]
            atr_val = df["atr"].iloc[i]

            sl_dist = atr_val * SL_ATR_MULT

            if direction == "LONG":
                sl = entry - sl_dist
                tp = entry + sl_dist * RR
            else:
                sl = entry + sl_dist
                tp = entry - sl_dist * RR

            future = df.iloc[entry_idx:entry_idx+future_bars]

            result = None

            for _, row in future.iterrows():

                if direction == "LONG":
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
                state = None
                i += 1
                continue

            r = result * (sl_dist / entry)

            r -= FEE * 2
            r -= SLIPPAGE

            equity *= (1 + r)
            curve.append(equity)

            trades.append(result > 0)

            state = None

        i += 1

    return trades, curve


# =========================
# RUN
# =========================
print("===== DYDX V6 STATE MACHINE REPORT =====")

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
