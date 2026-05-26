import ccxt
import pandas as pd
import requests
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["CHAT_ID"]
ZIGZAG_LEN     = 9
FIB_FACTOR     = 0.33
CANDLE_COUNT   = 300
TIMEFRAMES     = {
    "15m": "15 dakika",
    "1h":  "1 saat",
    "4h":  "4 saat",
}

# OKX perpetual parite listesi
PAIRS = [
    "BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT","OKB/USDT:USDT","XRP/USDT:USDT",
    "ADA/USDT:USDT","DOGE/USDT:USDT","SHIB/USDT:USDT","AVAX/USDT:USDT","LINK/USDT:USDT",
    "DOT/USDT:USDT","TRX/USDT:USDT","LTC/USDT:USDT","BCH/USDT:USDT","NEAR/USDT:USDT",
    "APT/USDT:USDT","SUI/USDT:USDT","ARB/USDT:USDT","OP/USDT:USDT","MATIC/USDT:USDT",
    "STX/USDT:USDT","TIA/USDT:USDT","SEI/USDT:USDT","INJ/USDT:USDT","FTM/USDT:USDT",
    "ATOM/USDT:USDT","ALGO/USDT:USDT","EGLD/USDT:USDT","IMX/USDT:USDT","FIL/USDT:USDT",
    "GRT/USDT:USDT","ICP/USDT:USDT","AXS/USDT:USDT","SAND/USDT:USDT","MANA/USDT:USDT",
    "THETA/USDT:USDT","FLOW/USDT:USDT","KAVA/USDT:USDT","ONE/USDT:USDT","CHZ/USDT:USDT",
    "MINA/USDT:USDT","CRV/USDT:USDT","AAVE/USDT:USDT","FET/USDT:USDT","RENDER/USDT:USDT",
    "WLD/USDT:USDT","AGIX/USDT:USDT","ARKM/USDT:USDT","LDO/USDT:USDT","MKR/USDT:USDT",
    "COMP/USDT:USDT","SNX/USDT:USDT","UNI/USDT:USDT","SUSHI/USDT:USDT","YFI/USDT:USDT",
    "1INCH/USDT:USDT","WOO/USDT:USDT","GMX/USDT:USDT","DYDX/USDT:USDT","ENS/USDT:USDT",
    "ANKR/USDT:USDT","OCEAN/USDT:USDT","GALA/USDT:USDT","ENJ/USDT:USDT","BLUR/USDT:USDT",
    "MASK/USDT:USDT","CYBER/USDT:USDT","STRK/USDT:USDT","PYTH/USDT:USDT","CELO/USDT:USDT",
    "LRC/USDT:USDT","QTUM/USDT:USDT","PEPE/USDT:USDT","FLOKI/USDT:USDT","WIF/USDT:USDT",
    "BONK/USDT:USDT","MEME/USDT:USDT","WAVES/USDT:USDT","ZIL/USDT:USDT","XMR/USDT:USDT",
    "ZEC/USDT:USDT","DASH/USDT:USDT","IOST/USDT:USDT","ONT/USDT:USDT","RVN/USDT:USDT",
    "NEO/USDT:USDT","HOT/USDT:USDT","XLM/USDT:USDT","DY/USDT:USDT","BNB/USDT:USDT",
]


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram hata: {e}")


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
            signals.append({"direction": new_market, "h0": h0, "h0i": h0i, "h1": h1, "h1i": h1i,
                             "l0": l0, "l0i": l0i, "l1": l1, "l1i": l1i})
            market = new_market
        if market == 1:
            l_idx += 1
        else:
            h_idx += 1
    return signals


def find_ob_bb(df, sig, zigzag_len=9):
    direction = sig["direction"]
    try:
        if direction == 1:
            h1i_pos = df.index.get_loc(sig["h1i"])
            l0i_pos = df.index.get_loc(sig["l0i"])
            l1i_pos = df.index.get_loc(sig["l1i"])
            ob_idx = None
            for i in range(h1i_pos, min(l0i_pos + zigzag_len, len(df))):
                if df["open"].iloc[i] > df["close"].iloc[i]:
                    ob_idx = i
            bb_idx = None
            for i in range(max(0, l1i_pos - zigzag_len), h1i_pos + 1):
                if df["open"].iloc[i] < df["close"].iloc[i]:
                    bb_idx = i
        else:
            l1i_pos = df.index.get_loc(sig["l1i"])
            h0i_pos = df.index.get_loc(sig["h0i"])
            h1i_pos = df.index.get_loc(sig["h1i"])
            ob_idx = None
            for i in range(l1i_pos, min(h0i_pos + zigzag_len, len(df))):
                if df["open"].iloc[i] < df["close"].iloc[i]:
                    ob_idx = i
            bb_idx = None
            for i in range(max(0, h1i_pos - zigzag_len), l1i_pos + 1):
                if df["open"].iloc[i] > df["close"].iloc[i]:
                    bb_idx = i
    except KeyError:
        return None

    if ob_idx is None or bb_idx is None:
        return None

    inter_top    = min(df["high"].iloc[ob_idx], df["high"].iloc[bb_idx])
    inter_bottom = max(df["low"].iloc[ob_idx],  df["low"].iloc[bb_idx])

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
        sig_time = df.loc[last_sig["l0i"], "ts"] if last_sig["direction"] == 1 else df.loc[last_sig["h0i"], "ts"]
        time_diff = (last_bar_time - sig_time).total_seconds()
        tf_seconds = {"15m": 900, "1h": 3600, "4h": 14400}
        if time_diff > tf_seconds[timeframe] * 10:
            return None
        result = find_ob_bb(df, last_sig, ZIGZAG_LEN)
        if result is None:
            return None
        inter_top, inter_bottom = result
        pair_name = symbol.replace("/USDT:USDT", "USDT.P")
        now = datetime.utcnow().strftime("%H:%M UTC")
        msg = (
            f"<b>{'🟢 BULLISH' if last_sig['direction']==1 else '🔴 BEARISH'} MSB Kesişimi!</b>\n"
            f"📊 Parite: <b>{pair_name}</b>\n"
            f"⏱ Timeframe: <b>{tf_label}</b>\n"
            f"📍 Bölge: <b>{inter_bottom:.4f} - {inter_top:.4f}</b>\n"
            f"🕐 Saat: {now}"
        )
        return msg
    except Exception as e:
        print(f"  Hata {symbol}: {e}")
        return None


def main():
    exchange = ccxt.okx({"options": {"defaultType": "swap"}})

    # Geçersiz pariteleri filtrele
    print("Pariteler kontrol ediliyor...")
    valid_pairs = []
    try:
        markets = exchange.load_markets()
        for p in PAIRS:
            if p in markets:
                valid_pairs.append(p)
            else:
                print(f"  Atlandı: {p}")
    except Exception as e:
        print(f"Market yükleme hatası: {e}")
        valid_pairs = PAIRS  # hata olursa listeyi direkt kullan

    print(f"{len(valid_pairs)} geçerli parite bulundu.")
    total_signals = 0

    for tf, tf_label in TIMEFRAMES.items():
        print(f"\n── {tf_label} taranıyor ──")
        tf_signals = 0
        for symbol in valid_pairs:
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
