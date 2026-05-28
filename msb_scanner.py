import ccxt
import pandas as pd
import numpy as np
import time

# ==========================
# SETTINGS
# ==========================
SYMBOL = "BTC/USDT:USDT"
TIMEFRAME = "1h"

LEVERAGE = 20
RISK_PER_TRADE_USD = 10
MAX_POSITION_USD = 100

RR = 1.8
CHECK_INTERVAL = 300

exchange = ccxt.okx({
    "apiKey": "0c806423-035a-4d5b-ba6e-f0929e08a3c6",
    "secret": "08858444BB69AA7D6846A83D41A09BD0",
    "password": "Nki-201419hak",
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"
    }
})

# ==========================
# HELPERS
# ==========================
def fetch():
    bars = exchange.fetch_ohlcv(
        SYMBOL,
        timeframe=TIMEFRAME,
        limit=300
    )

    return pd.DataFrame(
        bars,
        columns=["ts","o","h","l","c","v"]
    )


def atr(df, period=14):
    hl = df["h"] - df["l"]
    hc = np.abs(df["h"] - df["c"].shift())
    lc = np.abs(df["l"] - df["c"].shift())

    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
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

    side = trend(df)

    highs = df["h"].rolling(20).max()
    lows = df["l"].rolling(20).min()

    i = len(df) - 1

    c = df["c"].iloc[i]
    h = df["h"].iloc[i]
    l = df["l"].iloc[i]

    last_high = highs.iloc[i - 1]
    last_low = lows.iloc[i - 1]

    if side == "LONG":
        if c > last_high and l <= last_high:
            return "LONG"

    if side == "SHORT":
        if c < last_low and h >= last_low:
            return "SHORT"

    return None


def smart_stop(df, side):

    a = atr(df).iloc[-1]
    price = df["c"].iloc[-1]

    if side == "LONG":
        swing_low = df["l"].rolling(10).min().iloc[-2]
        return min(swing_low, price - a)

    swing_high = df["h"].rolling(10).max().iloc[-2]
    return max(swing_high, price + a)


def smart_tp(entry, sl, side):
    risk = abs(entry - sl)

    if side == "LONG":
        return entry + risk * RR

    return entry - risk * RR


def position_size(entry, sl):
    stop_distance = abs(entry - sl)

    if stop_distance <= 0:
        return 0

    qty = RISK_PER_TRADE_USD / stop_distance
    max_qty = MAX_POSITION_USD / entry

    return round(min(qty, max_qty), 6)


# ==========================
# POSITION SYNC
# ==========================
def get_position():
    try:
        positions = exchange.fetch_positions([SYMBOL])

        for p in positions:
            contracts = float(p.get("contracts") or 0)

            if contracts > 0:
                side = p["side"].upper()

                return {
                    "side": "LONG" if side == "LONG" else "SHORT",
                    "qty": contracts
                }

    except Exception as e:
        print("Position fetch error:", e)

    return None


def close_position(position):
    try:
        qty = position["qty"]

        if position["side"] == "LONG":
            exchange.create_market_sell_order(SYMBOL, qty)
        else:
            exchange.create_market_buy_order(SYMBOL, qty)

        print("Position closed")

    except Exception as e:
        print("Close error:", e)


def open_position(side, qty, sl, tp):

    params = {
        "tdMode": "isolated"
    }

    try:
        if side == "LONG":
            exchange.create_market_buy_order(
                SYMBOL,
                qty,
                params=params
            )
        else:
            exchange.create_market_sell_order(
                SYMBOL,
                qty,
                params=params
            )

        # TP/SL exchange side
        exchange.private_post_trade_order_algo({
            "instId": SYMBOL.replace("/", "-"),
            "tdMode": "isolated",
            "side": "sell" if side == "LONG" else "buy",
            "ordType": "oco",
            "sz": str(qty),
            "tpTriggerPx": str(tp),
            "tpOrdPx": "-1",
            "slTriggerPx": str(sl),
            "slOrdPx": "-1"
        })

        print(f"OPEN {side}")

    except Exception as e:
        print("Open error:", e)


# ==========================
# LEVERAGE
# ==========================
try:
    exchange.set_leverage(
        LEVERAGE,
        SYMBOL,
        params={
            "marginMode": "isolated"
        }
    )
except Exception as e:
    print("Leverage warning:", e)


# ==========================
# MAIN LOOP
# ==========================
print("BOT STARTED")

while True:

    try:
        df = fetch()
        price = df["c"].iloc[-1]

        sig = signal(df)
        pos = get_position()

        if sig is None:
            time.sleep(CHECK_INTERVAL)
            continue

        sl = smart_stop(df, sig)
        tp = smart_tp(price, sl, sig)
        qty = position_size(price, sl)

        if qty <= 0:
            time.sleep(CHECK_INTERVAL)
            continue

        # flip mode
        if pos is not None:

            if pos["side"] != sig:
                print("Flip:", pos["side"], "->", sig)
                close_position(pos)
                time.sleep(2)
                open_position(sig, qty, sl, tp)

        else:
            open_position(sig, qty, sl, tp)

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(10)
