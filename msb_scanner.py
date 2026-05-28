import requests
import pandas as pd
from datetime import datetime
import json
import os

# ==========================
# TELEGRAM AYARLARI
# ==========================
BOT_TOKEN = "8953905429:AAFAZRJ9d2u20wDD3F2BLU9-ThaWWiq4-A0"
CHAT_ID = "1599636303"

# ==========================
# AYARLAR
# ==========================
TIMEFRAMES = {
    "15m": "15m",
    "1H": "1H",
    "4H": "4H",
    "1D": "1D"
}

LIMIT = 200
ZIGZAG_LEN = 9
CACHE_FILE = "sent_signals.json"


# ==========================
# CACHE
# ==========================
def load_sent_signals():

    if not os.path.exists(CACHE_FILE):
        return {}

    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)

        # Eski bozuk format geldiyse sıfırla
        if not isinstance(data, dict):
            return {}

        return data

    except:
        return {}


def save_sent_signals(data):

    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass


# ==========================
# TELEGRAM
# ==========================
def send_telegram_message(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass


# ==========================
# OKX PARITELERI
# ==========================
def get_okx_pairs():

    url = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"

    try:
        response = requests.get(url, timeout=15).json()

        data = response.get("data", [])

        pairs = []

        for item in data:

            inst_id = item.get("instId")

            if inst_id and "USDT" in inst_id:
                pairs.append(inst_id)

        return pairs

    except:
        return []


# ==========================
# CANDLE VERISI
# ==========================
def get_candles(symbol, timeframe):

    url = (
        f"https://www.okx.com/api/v5/market/candles"
        f"?instId={symbol}&bar={timeframe}&limit={LIMIT}"
    )

    try:
        response = requests.get(url, timeout=15).json()

        rows = response.get("data", [])

        if len(rows) == 0:
            return None

        df = pd.DataFrame(rows, columns=[
            "ts",
            "open",
            "high",
            "low",
            "close",
            "vol",
            "volCcy",
            "volCcyQuote",
            "confirm"
        ])

        df = df[::-1].reset_index(drop=True)

        df["high"] = pd.to_numeric(df["high"], errors="coerce")
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")

        df.dropna(inplace=True)

        return df

    except:
        return None


# ==========================
# BASIT MSB
# ==========================
def detect_msb(df):

    if df is None or len(df) < 20:
        return None

    try:

        highs = df["high"].rolling(ZIGZAG_LEN).max()
        lows = df["low"].rolling(ZIGZAG_LEN).min()

        recent_high = highs.iloc[-1]
        previous_high = highs.iloc[-10]

        recent_low = lows.iloc[-1]
        previous_low = lows.iloc[-10]

        price = df["close"].iloc[-1]

        if recent_high > previous_high and price > previous_high:
            return "LONG"

        if recent_low < previous_low and price < previous_low:
            return "SHORT"

        return None

    except:
        return None


# ==========================
# TARAYICI
# ==========================
def scan():

    sent_signals = load_sent_signals()

    pairs = get_okx_pairs()

    print("SCAN BASLADI...\n")

    for tf_name, tf in TIMEFRAMES.items():

        print(f"\n===== {tf_name} =====")

        for pair in pairs:

            try:

                df = get_candles(pair, tf)

                signal = detect_msb(df)

                if not signal:
                    continue

                candle_time = str(df.iloc[-1]["ts"])

                signal_key = (
                    f"{pair}_"
                    f"{tf_name}_"
                    f"{signal}_"
                    f"{candle_time}"
                )

                # Aynı mum tekrar gönderilmesin
                if signal_key in sent_signals:
                    continue

                sent_signals[signal_key] = True

                saat = datetime.now().strftime("%H:%M")

                emoji = "🟢" if signal == "LONG" else "🔴"

                message = (
                    f"{emoji} {signal}\n\n"
                    f"Coin: {pair}\n"
                    f"TF: {tf_name}\n"
                    f"Saat: {saat}"
                )

                send_telegram_message(message)

                print(f"{pair} -> {signal}")

            except Exception as e:
                print(f"{pair} hata: {e}")

    save_sent_signals(sent_signals)


if __name__ == "__main__":
    scan()
