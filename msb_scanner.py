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

# Güç filtresi
STRENGTH_FILTER = {
    "15m": 0.002,   # %0.2
    "1H": 0.004,    # %0.4
    "4H": 0.008,    # %0.8
    "1D": 0.02      # %2 sert filtre
}

# Spam önleme
sent_signals = set()


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
# OKX PAIRLER
# ==========================
def get_okx_pairs():

    url = "https://www.okx.com/api/v5/public/instruments?instType=SWAP"

    try:

        r = requests.get(url, timeout=15).json()

        pairs = []

        for item in r.get("data", []):

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

        r = requests.get(url, timeout=15).json()

        rows = r.get("data", [])

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

        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df.dropna(inplace=True)

        return df

    except:
        return None


# ==========================
# GERÇEK YENİ MSB
# ==========================
def detect_msb(df, tf_name):

    global sent_signals

    if df is None or len(df) < 50:
        return None

    try:

        highs = df["high"].rolling(ZIGZAG_LEN).max()
        lows = df["low"].rolling(ZIGZAG_LEN).min()

        previous_high = highs.iloc[-10]
        previous_low = lows.iloc[-10]

        prev_candle = df.iloc[-2]
        current_candle = df.iloc[-1]

        prev_close = prev_candle["close"]
        current_close = current_candle["close"]

        current_low = current_candle["low"]
        current_high = current_candle["high"]

        candle_time = current_candle["ts"]

        filter_pct = STRENGTH_FILTER[tf_name]

        # ==========================
        # LONG
        # ==========================
        long_strength = (
            (current_close - previous_high)
            / previous_high
        )

        long_break = (
            prev_close <= previous_high
            and (
                current_close > previous_high
                or current_high > previous_high
            )
        )

        if long_break and long_strength >= filter_pct:

            signal_key = (
                f"LONG_"
                f"{tf_name}_"
                f"{round(previous_high,6)}_"
                f"{candle_time}"
            )

            if signal_key not in sent_signals:
                sent_signals.add(signal_key)
                return "LONG"

        # ==========================
        # SHORT
        # ==========================
        short_strength = (
            (previous_low - current_close)
            / previous_low
        )

        short_break = (
            prev_close >= previous_low
            and (
                current_close < previous_low
                or current_low < previous_low
            )
        )

        if short_break and short_strength >= filter_pct:

            signal_key = (
                f"SHORT_"
                f"{tf_name}_"
                f"{round(previous_low,6)}_"
                f"{candle_time}"
            )

            if signal_key not in sent_signals:
                sent_signals.add(signal_key)
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

        found = []

        for pair in pairs:

            try:

                df = get_candles(pair, tf)

                signal = detect_msb(df, tf_name)

                if signal is None:
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

                found.append(f"{pair} -> {signal}")

            except Exception as e:
                print(f"{pair} hata: {e}")

        if found:
            for item in found:
                print(item)
        else:
            print("Sinyal yok")


if __name__ == "__main__":
    scan()
