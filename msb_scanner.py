import ccxt
import pandas as pd
import numpy as np
import os
import time
import json

SYMBOL = "BTC/USDT:USDT"
TIMEFRAME = "1h"

LEVERAGE = 50
RISK_PER_TRADE_USD = 10
SAFE_RISK_USD = 5
RR = 1.8

STATE_FILE = "signal_state.json"

exchange = ccxt.okx({
    "apiKey": os.getenv("OKX_API_KEY"),
    "secret": os.getenv("OKX_SECRET"),
    "password": os.getenv("OKX_PASSWORD"),
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"
    }
})


# =========================
# STATE
# =========================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {
            "last_long_ts": None,
            "last_short_ts": None
        }

    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    except:
        return {
            "last_long_ts": None,
            "last_short_ts": None
        }


def save_state(state):

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# =========================
# DATA
# =========================

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
        return None, None

    direction = trend(df)

    highs = df["h"].rolling(20).max()
    lows = df["l"].rolling(20).min()

    i = len(df) - 1

    c = df["c"].iloc[i]
    h = df["h"].iloc[i]
    l = df["l"].iloc[i]

    last_high = highs.iloc[i - 1]
    last_low = lows.iloc[i - 1]

    candle_ts = int(df["ts"].iloc[i])

    if direction == "LONG":
        if c > last_high and l <= last_high:
            return "LONG", candle_ts

    if direction == "SHORT":
        if c < last_low and h >= last_low:
            return "SHORT", candle_ts

    return None, None


# =========================
# POSITION
# =========================

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

                return {
                    "side":
                    (
                        "LONG"
                        if p["side"].lower() == "long"
                        else "SHORT"
                    ),

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
                {
                    "tdMode":
                    "isolated"
                }
            )

        else:

            exchange.create_market_buy_order(
                SYMBOL,
                qty,
                {
                    "tdMode":
                    "isolated"
                }
            )

        print("POSITION CLOSED")

    except Exception as e:
        print("Close error:", e)


# =========================
# SL / TP
# =========================

def smart_stop(df, side):

    a = atr(df).iloc[-1]
    price = df["c"].iloc[-1]

    if side == "LONG":

        swing = (
            df["l"]
            .rolling(10)
            .min()
            .iloc[-2]
        )

        return min(
            swing,
            price - a
        )

    swing = (
        df["h"]
        .rolling(10)
        .max()
        .iloc[-2]
    )

    return max(
        swing,
        price + a
    )


def smart_tp(entry, sl, side):

    risk = abs(entry - sl)

    if side == "LONG":
        return entry + (risk * RR)

    return entry - (risk * RR)


# =========================
# RISK
# =========================

def estimate_liq_price(entry, side):

    move = entry / LEVERAGE

    if side == "LONG":
        return entry - move

    return entry + move


def risk_amount(entry, sl, side):

    liq = estimate_liq_price(
        entry,
        side
    )

    sl_gap = abs(entry - sl)
    liq_gap = abs(entry - liq)

    if liq_gap <= sl_gap * 1.3:

        print(
            "SAFE MODE: Risk 5 USD"
        )

        return SAFE_RISK_USD

    return RISK_PER_TRADE_USD


def position_size(entry, sl, side):

    dist = abs(entry - sl)

    if dist <= 0:
        return 0

    risk = risk_amount(
        entry,
        sl,
        side
    )

    qty = risk / dist

    return round(qty, 6)


def place_sl_tp(side, qty, sl, tp):

    try:

        params = {
            "tdMode": "isolated",

            "attachAlgoOrds": [
                {
                    # TP LIMIT
                    "tpTriggerPx":
                    str(round(tp, 2)),

                    "tpOrdPx":
                    str(round(tp, 2)),

                    # SL MARKET
                    "slTriggerPx":
                    str(round(sl, 2)),

                    "slOrdPx":
                    "-1"
                }
            ]
        }

        if side == "LONG":

            exchange.create_market_buy_order(
                SYMBOL,
                qty,
                params
            )

        else:

            exchange.create_market_sell_order(
                SYMBOL,
                qty,
                params
            )

        print(
            "TP LIMIT + SL MARKET"
        )

    except Exception as e:
        print("SL/TP error:", e)


def open_position(side, qty, sl, tp):

    try:

        if side == "LONG":

            exchange.create_market_buy_order(
                SYMBOL,
                qty,
                {
                    "tdMode":
                    "isolated"
                }
            )

        else:

            exchange.create_market_sell_order(
                SYMBOL,
                qty,
                {
                    "tdMode":
                    "isolated"
                }
            )

        print("OPEN", side)

        time.sleep(2)

        place_sl_tp(
            side,
            qty,
            sl,
            tp
        )

    except Exception as e:
        print("Open error:", e)


# =========================
# LEVERAGE
# =========================

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
    print(
        "Leverage warning:",
        e
    )


# =========================
# MAIN
# =========================

try:

    print(
        "===== BTC BOT START ====="
    )

    state = load_state()

    df = fetch()

    price = df["c"].iloc[-1]

    sig, candle_ts = signal(df)

    pos = get_position()

    print("Signal:", sig)
    print("Position:", pos)

    if sig:

        same_signal = (
            sig == "LONG"
            and state["last_long_ts"]
            == candle_ts
        ) or (
            sig == "SHORT"
            and state["last_short_ts"]
            == candle_ts
        )

        if same_signal:

            print(
                "SKIP SAME SIGNAL CANDLE"
            )

        else:

            sl = smart_stop(
                df,
                sig
            )

            tp = smart_tp(
                price,
                sl,
                sig
            )

            qty = position_size(
                price,
                sl,
                sig
            )

            print(
                "SL:",
                round(sl, 2)
            )

            print(
                "TP:",
                round(tp, 2)
            )

            print(
                "Qty:",
                qty
            )

            if pos:

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
                        "SAME POSITION"
                    )

            else:

                open_position(
                    sig,
                    qty,
                    sl,
                    tp
                )

            if sig == "LONG":
                state[
                    "last_long_ts"
                ] = candle_ts

            else:
                state[
                    "last_short_ts"
                ] = candle_ts

            save_state(state)

    print("===== DONE =====")

except Exception as e:
    print("ERROR:", e)

# scheduler wake
