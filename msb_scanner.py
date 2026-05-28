import requests
import pandas as pd
from datetime import datetime

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


# ==========================
# TELEGRAM MESAJ
# ==========================
def send_telegram_message(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    requests.post(url, data=payload)


# ==========================
# OKX PARITELERI
# ==========================
def get_okx_pairs():

    url = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"

    data = requests.get(url).json()

    pairs = []

    for x in data["data"]:

        inst_id = x["instId"]

        if "USDT" in inst_id:
            pairs.append(inst_id)

    return pairs


# ==========================
# CANDLE VERISI
# ==========================
def get_candles(symbol, timeframe):

    url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={timeframe}&limit={LIMIT}"

    r = requests.get(url).json()

    if "data" not in r:
        return None

    rows = r["data"]

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

    df = df[::-1]

    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)

    return df


# ==========================
# BASIT MSB ANALIZI
# ==========================
def detect_msb(df):

    highs = df["high"].rolling(ZIGZAG_LEN).max()
    lows = df["low"].rolling(ZIGZAG_LEN).min()

    recent_high = highs.iloc[-1]
    previous_high = highs.iloc[-10]

    recent_low = lows.iloc[-1]
    previous_low = lows.iloc[-10]

    price = df["close"].iloc[-1]

    if recent_high > previous_high and price > previous_high:
        return "LONG"

    elif recent_low < previous_low and price < previous_low:
        return "SHORT"

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

                if df is None:
                    continue

                signal = detect_msb(df)

                if signal:

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
                continue


if __name__ == "__main__":
    scan()
