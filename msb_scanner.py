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
    qty = max(qty, 0.01)

    return round(qty, 2)


def get_position():
    try:
        positions = exchange.fetch_positions([SYMBOL])

        for p in positions:
            if float(p.get("contracts") or 0) > 0:
                return {
                    "side": "LONG" if p["side"].lower() == "long" else "SHORT",
                    "qty": float(p["contracts"])
                }

    except Exception as e:
        print("Position error:", e)

    return None


def place_sl_tp(side, qty, sl, tp):
    try:
        params = {
            "tdMode": "isolated",
            "attachAlgoOrds": [
                {
                    "tpTriggerPx": str(round(tp, 2)),
                    "tpOrdPx": "-1",
                    "slTriggerPx": str(round(sl, 2)),
                    "slOrdPx": "-1"
                }
            ]
        }

        if side == "LONG":
            exchange.create_market_buy_order(SYMBOL, qty, params)
        else:
            exchange.create_market_sell_order(SYMBOL, qty, params)

        print("SL/TP ATTACHED OKX ALGO")

    except Exception as e:
        print("SL/TP ERROR:", e)


def open_position(side, qty, sl, tp):
    try:
        params = {"tdMode": "isolated"}

        if side == "LONG":
            exchange.create_market_buy_order(SYMBOL, qty, params)
        else:
            exchange.create_market_sell_order(SYMBOL, qty, params)

        print("OPEN", side)
        time.sleep(2)

        place_sl_tp(side, qty, sl, tp)

    except Exception as e:
        print("OPEN ERROR:", e)


try:
    exchange.set_leverage(
        LEVERAGE,
        SYMBOL,
        params={"marginMode": "isolated"}
    )
except Exception as e:
    print("Leverage warning:", e)


try:
    print("===== BTC BOT START =====")

    df = fetch()
    price = df["c"].iloc[-1]

    sig = "LONG"  # TEST MODE

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
