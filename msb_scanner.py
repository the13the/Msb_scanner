import ccxt
import pandas as pd
import numpy as np

PAIR = "DYDX/USDT:USDT"
TIMEFRAME = "1h"

MONTHS_BACK = 3
LIMIT = 500

PIVOT = 6
MIN_SWEEP_PCT = 0.002

ATR_LEN = 14
SL_ATR_MULT = 1.2
RR = 1.5

FEE = 0.0004
SLIPPAGE = 0.0002

exchange = ccxt.okx({
    "enableRateLimit": True,
    "options": {"defaultType": "swap"}
})


# ==========================
# DATA FETCH
# ==========================
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
        last = batch[-1][0]

        if last <= since:
            break

        since = last + tf_ms

    if not all_candles:
        return pd.DataFrame()

    df = pd.DataFrame(all_candles, columns=["ts", "o", "h", "l", "c", "v"])
    df.drop_duplicates("ts", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


# ==========================
# ATR CALC
# ==========================
def atr(df, length=14):
    high = df["h"]
    low = df["l"]
    close = df["c"]

    tr = np.maximum(
        high - low,
        np.maximum(
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        )
    )

    return tr.rolling(length).mean()


# ==========================
# SIGNAL
# ==========================
def signal(df):
    if len(df) < 100:
        return None

    highs = df["h"].values
    lows = df["l"].values
    close = df["c"].iloc[-1]

    swing_highs = []
    swing_lows = []

    for i in range(PIVOT, len(df) - PIVOT):
        if highs[i] == np.max(highs[i-PIVOT:i+PIVOT+1]):
            swing_highs.append(highs[i])

        if lows[i] == np.min(lows[i-PIVOT:i+PIVOT+1]):
            swing_lows.append(lows[i])

    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return None

    last_high = max(swing_highs[-2:])
    last_low = min(swing_lows[-2:])

    # TRUE SWEEP (wick + rejection)
    sweep_high = (
        df["h"].iloc[-1] > last_high and
        df["c"].iloc[-1] < last_high and
        (df["h"].iloc[-1] - last_high) / last_high > MIN_SWEEP_PCT
    )

    sweep_low = (
        df["l"].iloc[-1] < last_low and
        df["c"].iloc[-1] > last_low and
        (last_low - df["l"].iloc[-1]) / last_low > MIN_SWEEP_PCT
    )

    trend_up = swing_lows[-1] > swing_lows[-2] > swing_lows[-3]
    trend_down = swing_highs[-1] < swing_highs[-2] < swing_highs[-3]

    if trend_up and sweep_low:
        return "LONG"

    if trend_down and sweep_high:
        return "SHORT"

    return None


# ==========================
# BACKTEST
# ==========================
def backtest(df):
    df["atr"] = atr(df, ATR_LEN)

    trades = []
    equity = 1.0
    curve = [equity]
    peak = equity
    max_dd = 0

    future_bars = 12

    for i in range(100, len(df) - future_bars):

        sub = df.iloc[:i]
        side = signal(sub)

        if side is None:
            continue

        atr_val = sub["atr"].iloc[-1]
        if np.isnan(atr_val):
            continue

        entry = df["o"].iloc[i]  # NEXT CANDLE OPEN (FIXED)

        # SL / TP
        sl_dist = atr_val * SL_ATR_MULT

        if side == "LONG":
            sl = entry - sl_dist
            tp = entry + sl_dist * RR
        else:
            sl = entry + sl_dist
            tp = entry - sl_dist * RR

        future = df.iloc[i:i+future_bars]

        result = None

        for _, row in future.iterrows():

            # SL FIRST (REALISTIC PRIORITY)
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
            continue

        # FEES + SLIPPAGE
        pnl = result * (sl_dist / entry)

        pnl -= FEE * 2
        pnl -= SLIPPAGE

        equity *= (1 + pnl)
        curve.append(equity)

        peak = max(peak, equity)
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)

        trades.append(result > 0)

    return trades, curve, max_dd


# ==========================
# RUN
# ==========================
print("===== DYDX V2 REPORT =====")

df = fetch_data(PAIR, TIMEFRAME)

if df.empty:
    print("NO DATA")
    exit()

print("Candles:", len(df))

results, curve, max_dd = backtest(df)

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

    print(f"Max Drawdown: {round(max_dd*100, 2)}%")
    print(f"Final Equity: {round(curve[-1], 3)}")
