import ccxt
import pandas as pd
import numpy as np
import os
import time

SYMBOL = "BTC/USDT:USDT"
TIMEFRAME = "1h"

LEVERAGE = 20
RISK_PER_TRADE_USD = 2
MAX_POSITION_USD = 20
RR = 1.8

exchange = ccxt.okx({
    "apiKey": os.getenv("OKX_API_KEY"),
    "secret": os.getenv("OKX_SECRET"),
    "password": os.getenv("OKX_PASSWORD"),
    "enableRateLimit": True,
    "options": {"defaultType": "swap"}
})


def fetch():
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=300)
    return pd.DataFrame(bars, columns=["ts", "o", "h", "l", "c", "v"])


def atr(df, period=14):
    hl = df["h"] - df["l"]
    hc = np.abs(df["h"] - df["c"].shift())
    lc = np.abs(df["l"] - df["c"].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def smart_stop(df, side):
    a = atr(df).iloc[-1]
    price = df["c"].iloc[-1]

    if side == "LONG":
        swing = df["l"].rolling(10).min().iloc[-2]
        return min(swing, price - a)

    swing = df["h"].rolling(10).max().iloc[-2]
    return max(swing, price + a)


def smart_tp(entry, sl, side):
    risk = abs(entry - sl)
    return entry + risk * RR if side == "LONG" else entry - risk * RR


def position_size(entry, sl):
    dist = abs(entry - sl)
    if dist <= 0:
        return 0.01

    qty = RISK_PER_TRADE_USD / dist
    max_qty = MAX_POSITION_USD / entry

    qty = min(qty, max_qty)
    return max(qty, 0.01)


def get_position():
    try:
        pos = exchange.fetch_positions([SYMBOL])
        for p in pos:
            if float(p.get("contracts") or 0) > 0:
                return {
                    "side": "LONG" if p["side"].lower() == "long" else "SHORT",
                    "qty": float(p["contracts"])
                }
    except Exception as e:
        print("Position error:", e)
    return None


def close_position(position):
    qty = position["qty"]

    try:
        if position["side"] == "LONG":
            exchange.create_market_sell_order(SYMBOL, qty, {"tdMode": "isolated"})
        else:
            exchange.create_market_buy_order(SYMBOL, qty, {"tdMode": "isolated"})
    except Exception as e:
        print("Close error:", e)


def place_sl_tp(side, qty, sl, tp):
    try:
        # TAKE PROFIT
        if side == "LONG":
            exchange.create_order(
                SYMBOL,
                "limit",
                "sell",
                qty,
                round(tp, 2),
                {"tdMode": "isolated", "reduceOnly": True}
            )

            exchange.create_order(
                SYMBOL,
                "stop_market",
                "sell",
                qty,
                None,
                {"tdMode": "isolated", "stopPrice": round(sl, 2), "reduceOnly": True}
            )

        else:
            exchange.create_order(
                SYMBOL,
                "limit",
                "buy",
                qty,
                round(tp, 2),
                {"tdMode": "isolated", "reduceOnly": True}
            )

            exchange.create_order(
                SYMBOL,
                "stop_market",
                "buy",
                qty,
                None,
                {"tdMode": "isolated", "stopPrice": round(sl, 2), "reduceOnly": True}
            )

        print("SL/TP placed")

    except Exception as e:
        print("SL/TP error:", e)


def open_position(side, qty, sl, tp):
    try:
        if side == "LONG":
            exchange.create_market_buy_order(SYMBOL, qty, {"tdMode": "isolated"})
        else:
            exchange.create_market_sell_order(SYMBOL, qty, {"tdMode": "isolated"})

        print("OPEN", side)
        time.sleep(2)

        place_sl_tp(side, qty, sl, tp)

    except Exception as e:
        print("Open error:", e)


try:
    exchange.set_leverage(LEVERAGE, SYMBOL, params={"marginMode": "isolated"})
except Exception as e:
    print("Leverage warning:", e)


try:
    print("===== BTC BOT START =====")

    df = fetch()
    price = df["c"].iloc[-1]

    sig = "LONG"   # TEST MODE

    pos = get_position()

    print("Signal:", sig)
    print("Position:", pos)

    sl = smart_stop(df, sig)
    tp = smart_tp(price, sl, sig)
    qty = position_size(price, sl)

    print("SL:", round(sl, 2))
    print("TP:", round(tp, 2))
    print("Qty:", qty)

    if pos is None:
        open_position(sig, qty, sl, tp)
    else:
        print("Position already open")

    print("===== DONE =====")

except Exception as e:
    print("ERROR:", e)
