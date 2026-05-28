import requests
import pandas as pd
from datetime import datetime

# ==========================
# TELEGRAM
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

# Güç filtresi (%)
STRENGTH_FILTER = {
    "15m": 0.0015,   # %0.15
    "1H": 0.0030,    # %0.30
    "4H": 0.0060,    # %0.60
    "1D": 0.0150     # %1.5 -> sert filtre
}


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

        pairs = []

        for item in response.get("data", []):
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
# MSB + GÜÇ FILTRESI
# ==========================
def detect_msb(df, tf_name):

    if df is None or len(df) < 30:
        return None

    try:

        highs = df["high"].rolling(ZIGZAG_LEN).max()
        lows = df["low"].rolling(ZIGZAG_LEN).min()

        prev_price = df["close"].iloc[-2]
        current_price = df["close"].iloc[-1]

        previous_high = highs.iloc[-10]
        previous_low = lows.iloc[-10]

        filter_pct = STRENGTH_FILTER[tf_name]

        # LONG güç kontrolü
        long_strength = (
            (current_price - previous_high)
            / previous_high
        )

        # SHORT güç kontrolü
        short_strength = (
            (previous_low - current_price)
            / previous_low
        )

        # LONG
        if (
            current_price > previous_high
            and prev_price <= previous_high
            and long_strength >= filter_pct
        ):
            return "LONG"

        # SHORT
        if (
            current_price < previous_low
            and prev_price >= previous_low
            and short_strength >= filter_pct
        ):
            return "SHORT"

        return None

    except:
        return None


# ==========================
# TARAYICI
# ==========================
def scan():

    pairs = get_okx_pairs()

    print("SCAN BASLADI...\n")

    for tf_name, tf in TIMEFRAMES.items():

        print(f"\n===== {tf_name} =====")

        for pair in pairs:

            try:

                df = get_candles(pair, tf)

                signal = detect_msb(df, tf_name)

                if not signal:
                    continue

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


if __name__ == "__main__":
    scan()
