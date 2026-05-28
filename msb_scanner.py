import ccxt
import pandas as pd
import numpy as np

PAIR = "DYDX/USDT:USDT"

TIMEFRAMES = ["15m", "1h"]

MONTHS_BACK = 3
PIVOT = 5

SL_PCT = 0.01
RR = 1.3
LIMIT = 500

MIN_SWEEP_PCT = 0.0008

exchange = ccxt.okx({
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"
    }
})


def fetch_data(symbol, timeframe):

    now_ms = exchange.milliseconds()

    since = (
        now_ms
        - (
            MONTHS_BACK
            * 30
            * 24
            * 60
            * 60
            * 1000
        )
    )

    candles = []

    tf_ms = (
        15 * 60 * 1000
        if timeframe == "15m"
        else 60 * 60 * 1000
    )

    while since < now_ms:

        try:

            batch = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=since,
                limit=LIMIT
            )

            if not batch:
                break

            candles.extend(batch)

            last_ts = batch[-1][0]

            if last_ts <= since:
                break

            since = last_ts + tf_ms

        except Exception as e:

            print(
                "FETCH ERROR:",
                symbol,
                timeframe,
                e
            )

            break

    if len(candles) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(
        candles,
        columns=[
            "ts",
            "o",
            "h",
            "l",
            "c",
            "v"
        ]
    )

    df.drop_duplicates(
        subset=["ts"],
        inplace=True
    )

    df.reset_index(
        drop=True,
        inplace=True
    )

    return df


def signal(df):

    if len(df) < 50:
        return None

    highs = df["h"].values
    lows = df["l"].values
    close = df["c"].iloc[-1]

    swing_highs = []
    swing_lows = []

    for i in range(
        PIVOT,
        len(df) - PIVOT
    ):

        if highs[i] == np.max(
            highs[
                i-PIVOT:
                i+PIVOT+1
            ]
        ):
            swing_highs.append(
                highs[i]
            )

        if lows[i] == np.min(
            lows[
                i-PIVOT:
                i+PIVOT+1
            ]
        ):
            swing_lows.append(
                lows[i]
            )

    if (
        len(swing_highs) < 2
        or
        len(swing_lows) < 2
    ):
        return None

    last_high = max(
        swing_highs[-2:]
    )

    last_low = min(
        swing_lows[-2:]
    )

    sweep_high = (
        close > last_high
        and
        (
            abs(close - last_high)
            / last_high
        )
        > MIN_SWEEP_PCT
    )

    sweep_low = (
        close < last_low
        and
        (
            abs(close - last_low)
            / last_low
        )
        > MIN_SWEEP_PCT
    )

    trend_up = (
        swing_lows[-1]
        >
        swing_lows[-2]
    )

    trend_down = (
        swing_highs[-1]
        <
        swing_highs[-2]
    )

    if trend_up and sweep_low:
        return "LONG"

    if trend_down and sweep_high:
        return "SHORT"

    return None


def backtest(df, tf):

    trades = []

    future_bars = (
        24
        if tf == "15m"
        else 12
    )

    for i in range(
        50,
        len(df) - future_bars
    ):

        sub = df.iloc[:i]

        side = signal(sub)

        if side is None:
            continue

        entry = sub["c"].iloc[-1]

        if side == "LONG":

            tp = entry * (
                1 + (
                    SL_PCT * RR
                )
            )

            sl = entry * (
                1 - SL_PCT
            )

        else:

            tp = entry * (
                1 - (
                    SL_PCT * RR
                )
            )

            sl = entry * (
                1 + SL_PCT
            )

        result = False

        future = df.iloc[
            i:i+future_bars
        ]

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


print("===== DYDX V5 REPORT =====")

for tf in TIMEFRAMES:

    print(f"\n===== {tf.upper()} =====")

    print(
        "Loading",
        PAIR,
        tf
    )

    df = fetch_data(
        PAIR,
        tf
    )

    if df.empty:

        print("NO DATA")
        continue

    print(
        "Candles:",
        len(df)
    )

    results = backtest(
        df,
        tf
    )

    if len(results) == 0:

        print("NO SIGNAL")
        continue

    wins = sum(results)
    losses = len(results) - wins

    wr = round(
        (
            wins
            / len(results)
        ) * 100,
        2
    )

    print(
        f"{PAIR} "
        f"| Trades:{len(results)} "
        f"| Win:{wins} "
        f"Loss:{losses} "
        f"| WR:{wr}%"
    )
