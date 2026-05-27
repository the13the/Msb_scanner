import ccxt
import pandas as pd
import requests
import os
import json
import hashlib
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["CHAT_ID"]
ZIGZAG_LEN     = 9
FIB_FACTOR     = 0.33
CANDLE_COUNT   = 300
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
    """Sinyal için benzersiz ID oluştur."""
    key = f"{symbol}_{timeframe}_{direction}_{inter_top:.4f}_{inter_bottom:.4f}"
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


def scan_pair(exchange, symbol, timeframe, tf_label, sent_signals):
    try:
        df = fetch_ohlcv(exchange, symbol, timeframe, limit=CANDLE_COUNT)
        if len(df) < ZIGZAG_LEN * 3:
            return None, None
        high_pts, low_pts = compute_zigzag(df, ZIGZAG_LEN)
        if len(high_pts) < 2 or len(low_pts) < 2:
            return None, None
        signals = detect_msb(high_pts, low_pts, FIB_FACTOR)
        if not signals:
            return None, None
        last_sig = signals[-1]
        result = find_ob_bb(df, last_sig, ZIGZAG_LEN)
        if result is None:
            return None, None
        inter_top, inter_bottom = result

        # Sinyal ID oluştur, daha önce gönderildiyse atla
        sig_id = make_signal_id(symbol, timeframe, last_sig["direction"], inter_top, inter_bottom)
        if sig_id in sent_signals:
            return None, None

        pair_name = symbol.replace("/USDT:USDT", "USDT.P")
        now = datetime.utcnow().strftime("%H:%M UTC")
        msg = (
            f"<b>{'🟢 BULLISH' if last_sig['direction']==1 else '🔴 BEARISH'} MSB Kesişimi!</b>\n"
            f"📊 Parite: <b>{pair_name}</b>\n"
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
    print(f"Daha önce gönderilen sinyal sayısı: {len(sent_signals)}")

    print("Marketler yükleniyor...")
    try:
        markets = exchange.load_markets()
        valid_pairs = [p for p in PAIRS if p in markets]
        skipped = [p for p in PAIRS if p not in markets]
        if skipped:
            print(f"OKX'te olmayan: {', '.join(skipped)}")
    except Exception as e:
        print(f"Market yükleme hatası: {e}, liste direkt kullanılıyor.")
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

    # Gönderilen sinyalleri kaydet
    sent_signals.update(new_sent)
    # Listeyi max 10000 ile sınırla (çok büyümesin)
    if len(sent_signals) > 10000:
        sent_signals = set(list(sent_signals)[-10000:])
    save_sent_signals(sent_signals)

    if total_signals == 0:
        print("Yeni sinyal bulunamadı.")
    else:
        print(f"\nToplam {total_signals} yeni sinyal gönderildi.")


if __name__ == "__main__":
    main()
