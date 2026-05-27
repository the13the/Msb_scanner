import ccxt
import pandas as pd
import numpy as np
import requests
import os
import json
import hashlib
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["CHAT_ID"]
ZIGZAG_LEN     = 9
FIB_FACTOR     = 0.33
CANDLE_COUNT   = 500
SENT_FILE      = "sent_signals.json"
TIMEFRAMES     = {
    "15m": "15 dakika",
    "1h":  "1 saat",
    "4h":  "4 saat",
}

PAIRS = [
    "BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT","XRP/USDT:USDT","ADA/USDT:USDT",
    "AVAX/USDT:USDT","LINK/USDT:USDT","DOT/USDT:USDT","MATIC/USDT:USDT","POL/USDT:USDT",
    "TRX/USDT:USDT","LTC/USDT:USDT","BCH/USDT:USDT","ETC/USDT:USDT","ATOM/USDT:USDT",
    "XLM/USDT:USDT","NEAR/USDT:USDT","APT/USDT:USDT","SUI/USDT:USDT","TON/USDT:USDT",
    "ARB/USDT:USDT","OP/USDT:USDT","TIA/USDT:USDT","SEI/USDT:USDT","FET/USDT:USDT",
    "RENDER/USDT:USDT","RNDR/USDT:USDT","TAO/USDT:USDT","GRT/USDT:USDT","AGIX/USDT:USDT",
    "DOGE/USDT:USDT","SHIB/USDT:USDT","PEPE/USDT:USDT","WIF/USDT:USDT","BONK/USDT:USDT",
    "FLOKI/USDT:USDT","BOME/USDT:USDT","OKB/USDT:USDT","UNI/USDT:USDT","AAVE/USDT:USDT",
    "MKR/USDT:USDT","INJ/USDT:USDT","LDO/USDT:USDT","ICP/USDT:USDT","FIL/USDT:USDT",
    "HBAR/USDT:USDT","STX/USDT:USDT","IMX/USDT:USDT","VET/USDT:USDT","THETA/USDT:USDT",
    "RUNE/USDT:USDT","EGLD/USDT:USDT","ALGO/USDT:USDT","QNT/USDT:USDT","FLOW/USDT:USDT",
    "FTM/USDT:USDT","SAND/USDT:USDT","MANA/USDT:USDT","APE/USDT:USDT","AXS/USDT:USDT",
    "GALA/USDT:USDT","DYDX/USDT:USDT","CRV/USDT:USDT","CHZ/USDT:USDT","GMT/USDT:USDT",
    "MINA/USDT:USDT","KAVA/USDT:USDT","COMP/USDT:USDT","SNX/USDT:USDT","WOO/USDT:USDT",
    "JUP/USDT:USDT","PYTH/USDT:USDT","STRK/USDT:USDT","MANTA/USDT:USDT","ALT/USDT:USDT",
    "ENS/USDT:USDT","BLUR/USDT:USDT","MEME/USDT:USDT","ORDI/USDT:USDT","SATS/USDT:USDT",
    "TRB/USDT:USDT","GAS/USDT:USDT","AUDIO/USDT:USDT","MAGIC/USDT:USDT","SUSHI/USDT:USDT",
    "YFI/USDT:USDT","1INCH/USDT:USDT","ZRX/USDT:USDT","BAT/USDT:USDT","ENJ/USDT:USDT",
    "LRC/USDT:USDT","ANKR/USDT:USDT","KSM/USDT:USDT","QTUM/USDT:USDT","NEO/USDT:USDT",
    "ONT/USDT:USDT","IOST/USDT:USDT","ZIL/USDT:USDT","ICX/USDT:USDT","OMG/USDT:USDT",
    "WAVES/USDT:USDT","ONE/USDT:USDT","CELO/USDT:USDT","SKL/USDT:USDT","CHR/USDT:USDT",
    "API3/USDT:USDT","BAND/USDT:USDT","PENDLE/USDT:USDT","PHB/USDT:USDT","TRU/USDT:USDT",
    "LQTY/USDT:USDT","ID/USDT:USDT","AR/USDT:USDT","STORJ/USDT:USDT","BLZ/USDT:USDT",
    "PERP/USDT:USDT","OGN/USDT:USDT","GTC/USDT:USDT","BAL/USDT:USDT","BADGER/USDT:USDT",
    "ALPHA/USDT:USDT","BICO/USDT:USDT","FRONT/USDT:USDT","UNFI/USDT:USDT","BEL/USDT:USDT",
    "DIA/USDT:USDT","RSR/USDT:USDT","NMR/USDT:USDT","LPT/USDT:USDT","UMA/USDT:USDT",
    "REQ/USDT:USDT","STG/USDT:USDT","CORE/USDT:USDT","MEW/USDT:USDT","POPCAT/USDT:USDT",
    "BRETT/USDT:USDT","NOT/USDT:USDT","IO/USDT:USDT","ZK/USDT:USDT","OMNI/USDT:USDT",
    "TNSR/USDT:USDT","W/USDT:USDT","ENA/USDT:USDT","ETHFI/USDT:USDT","METIS/USDT:USDT",
    "AEVO/USDT:USDT","DYM/USDT:USDT","RON/USDT:USDT","GLM/USDT:USDT","JTO/USDT:USDT",
    "BIGTIME/USDT:USDT","BEAM/USDT:USDT","NTRN/USDT:USDT","CYBER/USDT:USDT","YGG/USDT:USDT",
    "WLD/USDT:USDT","ARK/USDT:USDT","LUNC/USDT:USDT","XVS/USDT:USDT","OXT/USDT:USDT",
    "RVN/USDT:USDT","FLM/USDT:USDT","ACH/USDT:USDT","DENT/USDT:USDT","CTSI/USDT:USDT",
    "KNC/USDT:USDT","MTL/USDT:USDT","CVC/USDT:USDT","CLV/USDT:USDT","FUN/USDT:USDT",
    "SC/USDT:USDT","SPELL/USDT:USDT","JASMY/USDT:USDT","PEOPLE/USDT:USDT","LUNA/USDT:USDT",
    "BAKE/USDT:USDT","PUNDIX/USDT:USDT",
]


def make_signal_id(symbol, timeframe, direction, inter_top, inter_bottom):
    key = f"{symbol}_{timeframe}_{direction}_{inter_top:.6f}_{inter_bottom:.6f}"
    return hashlib.md5(key.encode()).hexdigest()


def load_sent_signals():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_sent_signals(signals):
    with open(SENT_FILE, "w") as f:
        json.dump(list(signals), f)


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram hata: {e}")


def fetch_ohlcv(exchange, symbol, timeframe, limit=500):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.reset_index(drop=True)
    return df


def pine_msb_scan(df, zigzag_len=9, fib_factor=0.33):
    """
    Pine Script mantığını birebir taklit eder.
    Her bar için trend, market, zigzag hesaplar.
    Döner: son market değişiminde oluşan kesişim kutusu (varsa)
    """
    n = len(df)
    high  = df["high"].values
    low   = df["low"].values
    open_ = df["open"].values
    close = df["close"].values

    # --- ZigZag ---
    # Pine: to_up = high >= ta.highest(zigzag_len)
    #        to_down = low <= ta.lowest(zigzag_len)
    trend = np.ones(n, dtype=int)
    to_up   = np.zeros(n, dtype=bool)
    to_down = np.zeros(n, dtype=bool)

    for i in range(zigzag_len, n):
        highest = np.max(high[max(0, i - zigzag_len + 1): i + 1])
        lowest  = np.min(low[max(0,  i - zigzag_len + 1): i + 1])
        to_up[i]   = high[i] >= highest
        to_down[i] = low[i]  <= lowest

    for i in range(1, n):
        trend[i] = trend[i-1]
        if trend[i] == 1 and to_down[i]:
            trend[i] = -1
        elif trend[i] == -1 and to_up[i]:
            trend[i] = 1

    # --- High/Low points (zigzag tepe/dip noktaları) ---
    high_points = []  # (bar_index, value)
    low_points  = []

    for i in range(1, n):
        if trend[i] != trend[i-1]:
            if trend[i] == 1:
                # trend aşağıdan yukarıya döndü → dip noktası ekle
                since = 0
                for j in range(i, -1, -1):
                    if j == 0 or (trend[j] != trend[i] and j < i):
                        since = j
                        break
                window = low[since:i+1]
                min_idx = since + np.argmin(window)
                low_points.append((min_idx, low[min_idx]))
            else:
                # trend yukarıdan aşağıya döndü → tepe noktası ekle
                since = 0
                for j in range(i, -1, -1):
                    if j == 0 or (trend[j] != trend[i] and j < i):
                        since = j
                        break
                window = high[since:i+1]
                max_idx = since + np.argmax(window)
                high_points.append((max_idx, high[max_idx]))

    if len(high_points) < 2 or len(low_points) < 2:
        return None

    # --- Market Structure ---
    # Pine: market == 1 and l0 < l1 and l0 < l1 - abs(h0-l1)*fib → bearish MSB
    #        market == -1 and h0 > h1 and h0 > h1 + abs(h1-l0)*fib → bullish MSB

    market_changes = []  # (bar_index, direction, h0,h0i,h1,h1i,l0,l0i,l1,l1i)
    market = 1
    hi = 0
    li = 0

    while hi + 1 < len(high_points) and li + 1 < len(low_points):
        h0i, h0 = high_points[hi]
        h1i, h1 = high_points[hi+1]
        l0i, l0 = low_points[li]
        l1i, l1 = low_points[li+1]

        new_market = market
        if market == 1 and l0 < l1 and l0 < l1 - abs(h0 - l1) * fib_factor:
            new_market = -1
        elif market == -1 and h0 > h1 and h0 > h1 + abs(h1 - l0) * fib_factor:
            new_market = 1

        if new_market != market:
            market_changes.append({
                "direction": new_market,
                "h0": h0, "h0i": h0i,
                "h1": h1, "h1i": h1i,
                "l0": l0, "l0i": l0i,
                "l1": l1, "l1i": l1i,
            })
            market = new_market

        if market == 1:
            li += 1
        else:
            hi += 1

    if not market_changes:
        return None

    last = market_changes[-1]
    direction = last["direction"]

    # --- OB ve BB/MB bul (Pine Script mantığı) ---
    if direction == 1:  # Bullish MSB
        # Bu-OB: h1i → l0i+zigzag_len arasındaki son bearish mum
        bu_ob_idx = None
        for i in range(last["h1i"], min(last["l0i"] + zigzag_len, n)):
            if open_[i] > close[i]:
                bu_ob_idx = i

        # Bu-BB: l1i-zigzag_len → h1i arasındaki son bullish mum
        bu_bb_idx = None
        for i in range(max(0, last["l1i"] - zigzag_len), last["h1i"] + 1):
            if open_[i] < close[i]:
                bu_bb_idx = i

        if bu_ob_idx is None or bu_bb_idx is None:
            return None

        ob_top    = high[bu_ob_idx]
        ob_bottom = low[bu_ob_idx]
        bb_top    = high[bu_bb_idx]
        bb_bottom = low[bu_bb_idx]
        bb_type   = "BB" if last["l0"] < last["l1"] else "MB"

    else:  # Bearish MSB
        # Be-OB: l1i → h0i+zigzag_len arasındaki son bullish mum
        be_ob_idx = None
        for i in range(last["l1i"], min(last["h0i"] + zigzag_len, n)):
            if open_[i] < close[i]:
                be_ob_idx = i

        # Be-BB: h1i-zigzag_len → l1i arasındaki son bearish mum
        be_bb_idx = None
        for i in range(max(0, last["h1i"] - zigzag_len), last["l1i"] + 1):
            if open_[i] > close[i]:
                be_bb_idx = i

        if be_ob_idx is None or be_bb_idx is None:
            return None

        ob_top    = high[be_ob_idx]
        ob_bottom = low[be_ob_idx]
        bb_top    = high[be_bb_idx]
        bb_bottom = low[be_bb_idx]
        bb_type   = "BB" if last["h0"] > last["h1"] else "MB"

    # Kesişim hesabı
    inter_top    = min(ob_top, bb_top)
    inter_bottom = max(ob_bottom, bb_bottom)

    if inter_top <= inter_bottom:
        return None

    return {
        "direction":    direction,
        "inter_top":    inter_top,
        "inter_bottom": inter_bottom,
        "bb_type":      bb_type,
        "msb_bar":      last["h0i"] if direction == 1 else last["l0i"],
    }


def scan_pair(exchange, symbol, timeframe, tf_label, sent_signals):
    try:
        df = fetch_ohlcv(exchange, symbol, timeframe, limit=CANDLE_COUNT)
        if len(df) < ZIGZAG_LEN * 5:
            return None, None

        result = pine_msb_scan(df, ZIGZAG_LEN, FIB_FACTOR)
        if result is None:
            return None, None

        sig_id = make_signal_id(symbol, timeframe, result["direction"],
                                result["inter_top"], result["inter_bottom"])
        if sig_id in sent_signals:
            return None, None

        direction  = result["direction"]
        inter_top  = result["inter_top"]
        inter_bottom = result["inter_bottom"]
        bb_type    = result["bb_type"]
        pair_name  = symbol.replace("/USDT:USDT", "USDT.P")
        now        = datetime.utcnow().strftime("%H:%M UTC")
        label      = f"Bu-OB-{bb_type}" if direction == 1 else f"Be-OB-{bb_type}"

        msg = (
            f"<b>{'🟢 BULLISH' if direction==1 else '🔴 BEARISH'} MSB Kesişimi!</b>\n"
            f"📊 Parite: <b>{pair_name}</b>\n"
            f"📦 Kutu: <b>{label}</b>\n"
            f"⏱ Timeframe: <b>{tf_label}</b>\n"
            f"📍 Bölge: <b>{inter_bottom:.4f} - {inter_top:.4f}</b>\n"
            f"🕐 Saat: {now}"
        )
        return msg, sig_id

    except Exception as e:
        print(f"  Hata {symbol}: {e}")
        return None, None


def main():
    exchange = ccxt.okx({"options": {"defaultType": "swap"}})
    sent_signals = load_sent_signals()
    print(f"Daha önce gönderilen: {len(sent_signals)} sinyal")

    print("Marketler yükleniyor...")
    try:
        markets = exchange.load_markets()
        valid_pairs = [p for p in PAIRS if p in markets]
        skipped = [p for p in PAIRS if p not in markets]
        if skipped:
            print(f"OKX'te olmayan ({len(skipped)}): {', '.join(skipped)}")
    except Exception as e:
        print(f"Market yükleme hatası: {e}")
        valid_pairs = PAIRS

    print(f"{len(valid_pairs)} parite taranacak.")
    total_signals = 0
    new_sent = set()

    for tf, tf_label in TIMEFRAMES.items():
        print(f"\n── {tf_label} taranıyor ──")
        tf_signals = 0
        for symbol in valid_pairs:
            msg, sig_id = scan_pair(exchange, symbol, tf, tf_label, sent_signals)
            if msg and sig_id:
                print(f"  ✅ Yeni sinyal: {symbol}")
                send_telegram(msg)
                new_sent.add(sig_id)
                tf_signals += 1
                total_signals += 1
        print(f"  {tf_label}: {tf_signals} yeni sinyal.")

    sent_signals.update(new_sent)
    if len(sent_signals) > 10000:
        sent_signals = set(list(sent_signals)[-10000:])
    save_sent_signals(sent_signals)

    if total_signals == 0:
        print("Yeni sinyal bulunamadı.")
    else:
        print(f"\nToplam {total_signals} yeni sinyal gönderildi.")


if __name__ == "__main__":
    main()
