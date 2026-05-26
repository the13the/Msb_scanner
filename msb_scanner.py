import ccxt
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["CHAT_ID"]
ZIGZAG_LEN     = 9
FIB_FACTOR     = 0.33
TOP_N          = 100
TIMEFRAMES     = {
    "15m": "15 dakika",
    "1h":  "1 saat",
    "4h":  "4 saat",
}
CANDLE_COUNT   = 300

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_top_pairs(exchange, n=100):
    tickers = exchange.fetch_tickers()
    swaps = {k: v for k, v in tickers.items() if k.endswith("/USDT:USDT") and v.get("quoteVolume")}
    sorted_pairs = sorted(swaps, key=lambda x: swaps[x]["quoteVolume"] or 0, reverse=True)
    return sorted_pairs[:n]

def fetch_ohlcv(exchange, symbol, timeframe, limit=300):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

def compute_zigzag(df, length=9):
    high_pts, low_pts = [], []
    trend = 1
    for i in range(length, len(df)):
        window_h = df["high"].iloc[i - length: i + 1].max()
        window_l = df["low"].iloc[i - length: i + 1].min()
        to_up   = df["high"].iloc[i] >= window_h
        to_down = df["low"].iloc[i]  <= window_l
        prev_trend = trend
        if trend == 1 and to_down:
            trend = -1
        elif trend == -1 and to_up:
            trend = 1
        if trend != prev_trend:
            if trend == 1:
                low_val = df["low"].iloc[max(0, i - length): i + 1].min()
                low_idx = df["low"].iloc[max(0, i - length): i + 1].idxmin()
                low_pts.append((low_idx, low_val))
            else:
                high_val = df["high"].iloc[max(0, i - length): i + 1].max()
                high_idx = df["high"].iloc[max(0, i - length): i + 1].idxmax()
                high_pts.append((high_idx, high_val))
    return high_pts, low_pts

def detect_msb(high_pts, low_pts, fib=0.33):
    signals = []
    market = 1
    h_idx = 0
    l_idx = 0
    while h_idx + 1 < len(high_pts) and l_idx + 1 < len(low_pts):
        h0i, h0 = high_pts[h_idx]
        h1i, h1 = high_pts[h_idx + 1] if h_idx + 1 < len(high_pts) else (h0i, h0)
        l0i, l0 = low_pts[l_idx]
        l1i, l1 = low_pts[l_idx + 1] if l_idx + 1 < len(low_pts) else (l0i, l0)
        new_market = market
        if market == 1 and l0 < l1 and l0 < l1 - abs(h0 - l1) * fib:
            new_market = -1
        elif market == -1 and h0 > h1 and h0 > h1 + abs(h1 - l0) * fib:
            new_market = 1
        if new_market != market:
            signals.append({"direction": new_market, "h0": h0, "h0i": h0i, "h1": h1, "h1i": h1i, "l0": l0, "l0i": l0i, "l1": l1, "l1i": l1i})
            market = new_market
        if market == 1:
            l_idx += 1
        else:
            h_idx += 1
    return signals

def find_ob_bb(df, sig, zigzag_len=9):
    direction = sig["direction"]
    if direction == 1:
        try:
            h1i_pos = df.index.get_loc(sig["h1i"])
            l0i_pos = df.index.get_loc(sig["l0i"])
            l1i_pos = df.index.get_loc(sig["l1i"])
        except KeyError:
            return None
        ob_idx = None
        for i in range(h1i_pos, min(l0i_pos + zigzag_len, len(df))):
            if df["open"].iloc[i] > df["close"].iloc[i]:
                ob_idx = i
        bb_idx = None
        for i in range(max(0, l1i_pos - zigzag_len), h1i_pos + 1):
            if df["open"].iloc[i] < df["close"].iloc[i]:
                bb_idx = i
    else:
        try:
            l1i_pos = df.index.get_loc(sig["l1i"])
            h0i_pos = df.index.get_loc(sig["h0i"])
            h1i_pos = df.index.get_loc(sig["h1i"])
        except KeyError:
            return None
        ob_idx = None
        for i in range(l1i_pos, min(h0i_pos + zigzag_len, len(df))):
            if df["open"].iloc[i] < df["close"].iloc[i]:
                ob_idx = i
        bb_idx = None
        for i in range(max(0, h1i_pos - zigzag_len), l1i_pos + 1):
            if df["open"].iloc[i] > df["close"].iloc[i]:
                bb_idx = i
    if ob_idx is None or bb_idx is None:
        return None
    ob_top    = df["high"].iloc[ob_idx]
    ob_bottom = df["low"].iloc[ob_idx]
    bb_top    = df["high"].iloc[bb_idx]
    bb_bottom = df["low"].iloc[bb_idx]
    inter_top    = min(ob_top, bb_top)
    inter_bottom = max(ob_bottom, bb_bottom)
    if inter_top <= inter_bottom:
        return None
    return inter_top, inter_bottom

def scan_pair(exchange, symbol, timeframe, tf_label):
    try:
        df = fetch_ohlcv(exchange, symbol, timeframe, limit=CANDLE_COUNT)
        if len(df) < ZIGZAG_LEN * 3:
            return None
        high_pts, low_pts = compute_zigzag(df, ZIGZAG_LEN)
        if len(high_pts) < 2 or len(low_pts) < 2:
            return None
        signals = detect_msb(high_pts, low_pts, FIB_FACTOR)
        if not signals:
            return None
        last_sig = signals[-1]
        last_bar_time = df["ts"].iloc[-1]
        if last_sig["direction"] == 1:
            sig_time = df.loc[last_sig["l0i"], "ts"] if last_sig["l0i"] in df.index else None
        else:
            sig_time = df.loc[last_sig["h0i"], "ts"] if last_sig["h0i"] in df.index else None
        if sig_time is None:
            return None
        time_diff = (last_bar_time - sig_time).total_seconds()
        tf_seconds = {"15m": 900, "1h": 3600, "4h": 14400}
        if time_diff > tf_seconds[timeframe] * 10:
            return None
        result = find_ob_bb(df, last_sig, ZIGZAG_LEN)
        if result is None:
            return None
        inter_top, inter_bottom = result
        pair_name = symbol.replace("/USDT:USDT", "USDT")
        now = datetime.utcnow().strftime("%H:%M UTC")
        msg = (
            f"<b>{'🟢 BULLISH' if last_sig['direction']==1 else '🔴 BEARISH'} MSB Kesişimi!</b>\n"
            f"📊 Parite: <b>{pair_name}</b>\n"
            f"⏱ Timeframe: <b>{tf_label}</b>\n"
            f"📍 Bölge: <b>{inter_bottom:.4f} - {inter_top:.4f}</b>\n"
            f"🕐 Saat: {now}"
        )
        return msg
    except Exception:
        return None

def main():
    exchange = ccxt.okx({"options": {"defaultType": "swap"}})
    print("Pariteler çekiliyor...")
    try:
        pairs = get_top_pairs(exchange, TOP_N)
    except Exception as e:
        send_telegram(f"⚠️ OKX bağlantı hatası: {e}")
        return
    print(f"{len(pairs)} parite bulundu.")
    total_signals = 0
    for tf, tf_label in TIMEFRAMES.items():
        print(f"\n── {tf_label} taranıyor ──")
        tf_signals = 0
        for symbol in pairs:
            msg = scan_pair(exchange, symbol, tf, tf_label)
            if msg:
                print(f"  ✅ Sinyal: {symbol}")
                send_telegram(msg)
                tf_signals += 1
                total_signals += 1
        print(f"  {tf_label}: {tf_signals} sinyal.")
    if total_signals == 0:
        print("Hiç sinyal bulunamadı.")
    else:
        print(f"\nToplam {total_signals} sinyal gönderildi.")

if __name__ == "__main__":
    main()
