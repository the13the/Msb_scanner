
import ccxt
import pandas as pd
import numpy as np
import os
import time

SYMBOL = "BTC/USDT:USDT"
TIMEFRAME = "1h"

LEVERAGE = 20
RISK_PER_TRADE_USD = 10
MAX_POSITION_USD = 100
RR = 1.8

exchange = ccxt.okx({
    "apiKey": os.getenv("OKX_API_KEY"),
    "secret": os.getenv("OKX_SECRET"),
    "password": os.getenv("OKX_PASSWORD"),
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"
    }
})


def fetch():

    bars = exchange.fetch_ohlcv(
        SYMBOL,
        timeframe=TIMEFRAME,
        limit=300
    )

    return pd.DataFrame(
        bars,
        columns=[
            "ts",
            "o",
            "h",
            "l",
            "c",
            "v"
        ]
    )


def atr(df, period=14):

    hl = df["h"] - df["l"]
    hc = np.abs(df["h"] - df["c"].shift())
    lc = np.abs(df["l"] - df["c"].shift())

    tr = pd.concat(
        [hl, hc, lc],
        axis=1
    ).max(axis=1)

    return tr.rolling(period).mean()


def trend(df):

    ma50 = df["c"].rolling(50).mean()
    ma200 = df["c"].rolling(200).mean()

    if ma50.iloc[-1] > ma200.iloc[-1]:
        return "LONG"

    return "SHORT"


def signal(df):

    if len(df) < 200:
        return None

    direction = trend(df)

    highs = df["h"].rolling(20).max()
    lows = df["l"].rolling(20).min()

    i = len(df) - 1

    c = df["c"].iloc[i]
    h = df["h"].iloc[i]
    l = df["l"].iloc[i]

    last_high = highs.iloc[i - 1]
    last_low = lows.iloc[i - 1]

    if direction == "LONG":
        if c > last_high and l <= last_high:
            return "LONG"

    if direction == "SHORT":
        if c < last_low and h >= last_low:
            return "SHORT"

    return None


def smart_stop(df, side):

    a = atr(df).iloc[-1]
    price = df["c"].iloc[-1]

    if side == "LONG":

        swing_low = (
            df["l"]
            .rolling(10)
            .min()
            .iloc[-2]
        )

        return min(
            swing_low,
            price - a
        )

    swing_high = (
        df["h"]
        .rolling(10)
        .max()
        .iloc[-2]
    )

    return max(
        swing_high,
        price + a
    )


def smart_tp(entry, sl, side):

    risk = abs(entry - sl)

    if side == "LONG":
        return entry + (risk * RR)

    return entry - (risk * RR)


def position_size(entry, sl):

    stop_distance = abs(entry - sl)

    if stop_distance <= 0:
        return 0

    qty_by_risk = (
        RISK_PER_TRADE_USD
        / stop_distance
    )

    max_qty = (
        MAX_POSITION_USD
        / entry
    )

    qty = min(
        qty_by_risk,
        max_qty
    )

    return round(qty, 6)


def get_position():

    try:

        positions = exchange.fetch_positions(
            [SYMBOL]
        )

        for p in positions:

            contracts = float(
                p.get("contracts") or 0
            )

            if contracts > 0:

                side = p["side"]

                return {
                    "side":
                    "LONG"
                    if side.lower() == "long"
                    else "SHORT",

                    "qty":
                    contracts
                }

    except Exception as e:
        print("Position error:", e)

    return None


def close_position(position):

    qty = position["qty"]

    try:

        if position["side"] == "LONG":

            exchange.create_market_sell_order(
                SYMBOL,
                qty,
                params={
                    "tdMode": "isolated"
                }
            )

        else:

            exchange.create_market_buy_order(
                SYMBOL,
                qty,
                params={
                    "tdMode": "isolated"
                }
            )

        print("Position closed")

    except Exception as e:
        print("Close error:", e)


def place_tp_sl(side, qty, sl, tp):

    try:

        if side == "LONG":

            exchange.create_order(
                SYMBOL,
                "market",
                "sell",
                qty,
                None,
                {
                    "tdMode": "isolated",
                    "stopLossPrice": round(sl, 2),
                    "takeProfitPrice": round(tp, 2),
                    "reduceOnly": True
                }
            )

        else:

            exchange.create_order(
                SYMBOL,
                "market",
                "buy",
                qty,
                None,
                {
                    "tdMode": "isolated",
                    "stopLossPrice": round(sl, 2),
                    "takeProfitPrice": round(tp, 2),
                    "reduceOnly": True
                }
            )

        print("SL/TP placed")

    except Exception as e:
        print("SL TP error:", e)


def open_position(side, qty, sl, tp):

    try:

        if side == "LONG":

            exchange.create_market_buy_order(
                SYMBOL,
                qty,
                params={
                    "tdMode": "isolated"
                }
            )

        else:

            exchange.create_market_sell_order(
                SYMBOL,
                qty,
                params={
                    "tdMode": "isolated"
                }
            )

        print("OPEN", side)

        time.sleep(2)

        place_tp_sl(
            side,
            qty,
            sl,
            tp
        )

    except Exception as e:
        print("Open error:", e)


try:

    exchange.set_leverage(
        LEVERAGE,
        SYMBOL,
        params={
            "marginMode":
            "isolated"
        }
    )

except Exception as e:
    print("Leverage warning:", e)


try:

    print("===== BTC BOT START =====")

    df = fetch()

    price = df["c"].iloc[-1]
    sig = signal(df)
    pos = get_position()

    print("Signal:", sig)
    print("Position:", pos)

    if sig is not None:

        sl = smart_stop(df, sig)

        tp = smart_tp(
            price,
            sl,
            sig
        )

        qty = position_size(
            price,
            sl
        )

        print("SL:", round(sl, 2))
        print("TP:", round(tp, 2))
        print("Qty:", qty)

        if qty > 0:

            if pos is not None:

                if pos["side"] != sig:

                    print(
                        "FLIP:",
                        pos["side"],
                        "->",
                        sig
                    )

                    close_position(pos)

                    time.sleep(2)

                    open_position(
                        sig,
                        qty,
                        sl,
                        tp
                    )

                else:

                    print(
                        "Same position open"
                    )

            else:

                open_position(
                    sig,
                    qty,
                    sl,
                    tp
                )

    print("===== DONE =====")

except Exception as e:
    print("ERROR:", e)
