import ccxt
import pandas as pd
import numpy as np
import os
import time
import json
import requests

# =========================
# CONFIG — Her parite kendi ayarıyla
# =========================

COINS = [
    {"symbol": "BTC/USDT:USDT", "risk": 20, "state": "state_btc.json"},
    {"symbol": "ETH/USDT:USDT", "risk": 10, "state": "state_eth.json"},
]

TIMEFRAME   = "1h"
MAX_LEVERAGE = 50
RR          = 1.8
LIQ_SAFETY  = 1.5

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# =========================
# TELEGRAM
# =========================

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram token/chat_id yok.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

# =========================
# EXCHANGE
# =========================

exchange = ccxt.okx({
    "apiKey": os.getenv("OKX_API_KEY"),
    "secret": os.getenv("OKX_SECRET"),
    "password": os.getenv("OKX_PASSWORD"),
    "enableRateLimit": True,
    "options": {"defaultType": "swap"}
})

# =========================
# STATE
# =========================

def load_state(path):
    if not os.path.exists(path):
        return {"last_long_ts": None, "last_short_ts": None}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {"last_long_ts": None, "last_short_ts": None}

def save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f)

# =========================
# DATA / BAKİYE
# =========================

def fetch(symbol):
    bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=300)
    return pd.DataFrame(bars, columns=["ts", "o", "h", "l", "c", "v"])

def get_balance():
    try:
        bal = exchange.fetch_balance()
        usdt = bal.get("USDT", {})
        return float(usdt.get("free") or usdt.get("total") or 0)
    except Exception as e:
        print("Balance error:", e)
        return 0

# =========================
# INDICATORS
# =========================

def atr(df, period=14):
    hl = df["h"] - df["l"]
    hc = np.abs(df["h"] - df["c"].shift())
    lc = np.abs(df["l"] - df["c"].shift())
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def trend(df):
    ma50  = df["c"].rolling(50).mean()
    ma200 = df["c"].rolling(200).mean()
    return "LONG" if ma50.iloc[-1] > ma200.iloc[-1] else "SHORT"

def signal(df):
    if len(df) < 200:
        return None, None
    direction = trend(df)
    highs = df["h"].rolling(20).max()
    lows  = df["l"].rolling(20).min()
    i = len(df) - 1
    c = df["c"].iloc[i]; h = df["h"].iloc[i]; l = df["l"].iloc[i]
    last_high = highs.iloc[i - 1]; last_low = lows.iloc[i - 1]
    candle_ts = int(df["ts"].iloc[i])
    if direction == "LONG" and c > last_high and l <= last_high:
        return "LONG", candle_ts
    if direction == "SHORT" and c < last_low and h >= last_low:
        return "SHORT", candle_ts
    return None, None

# =========================
# POSITION
# =========================

def get_position(symbol):
    try:
        positions = exchange.fetch_positions([symbol])
        for p in positions:
            contracts = float(p.get("contracts") or 0)
            if contracts > 0:
                return {
                    "side": "LONG" if p["side"].lower() == "long" else "SHORT",
                    "qty": contracts
                }
    except Exception as e:
        print("Position error:", e)
    return None

def close_position(symbol, position):
    qty = position["qty"]
    try:
        if position["side"] == "LONG":
            exchange.create_market_sell_order(symbol, qty, {"tdMode": "isolated", "reduceOnly": True})
        else:
            exchange.create_market_buy_order(symbol, qty, {"tdMode": "isolated", "reduceOnly": True})
        print("POSITION CLOSED", symbol)
    except Exception as e:
        print("Close error:", e)

# =========================
# SL / TP
# =========================

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
    return entry + (risk * RR) if side == "LONG" else entry - (risk * RR)

# =========================
# KALDIRAÇ / RISK
# =========================

def calc_safe_leverage(entry, sl):
    sl_gap = abs(entry - sl)
    if sl_gap <= 0:
        return 1
    desired_liq_gap = sl_gap * LIQ_SAFETY
    lev = entry / desired_liq_gap
    return max(1, min(int(lev), MAX_LEVERAGE))

def estimate_liq_price(entry, side, leverage):
    move = entry / leverage
    return (entry - move) if side == "LONG" else (entry + move)

def position_size(entry, sl, risk_usd):
    dist = abs(entry - sl)
    if dist <= 0:
        return 0
    qty = risk_usd / dist
    return round(max(qty, 0.001), 6)

# =========================
# OPEN POSITION
# =========================

def open_position(symbol, side, qty, sl, tp):
    try:
        params = {
            "tdMode": "isolated",
            "attachAlgoOrds": [{
                "tpTriggerPx": str(round(tp, 2)),
                "tpOrdPx":     "-1",
                "slTriggerPx": str(round(sl, 2)),
                "slOrdPx":     "-1"
            }]
        }
        if side == "LONG":
            exchange.create_market_buy_order(symbol, qty, params)
        else:
            exchange.create_market_sell_order(symbol, qty, params)
        print("OPEN", symbol, side)
    except Exception as e:
        print("Open error:", e)
        send_telegram(f"⚠️ <b>{symbol} işlem açma hatası</b>\n<code>{str(e)[:200]}</code>")

# =========================
# TEK PARİTE İŞLE
# =========================

def process_coin(coin):
    symbol   = coin["symbol"]
    risk_usd = coin["risk"]
    state_f  = coin["state"]
    name     = symbol.split("/")[0]   # BTC, ETH

    print(f"\n----- {name} -----")

    state = load_state(state_f)
    df    = fetch(symbol)
    price = df["c"].iloc[-1]

    sig, candle_ts = signal(df)
    pos = get_position(symbol)

    print(f"{name} Signal:", sig, "| Position:", pos)

    if not sig:
        return

    same_signal = (
        sig == "LONG" and state["last_long_ts"] == candle_ts
    ) or (
        sig == "SHORT" and state["last_short_ts"] == candle_ts
    )
    if same_signal:
        print("SKIP SAME SIGNAL CANDLE")
        return

    sl  = smart_stop(df, sig)
    tp  = smart_tp(price, sl, sig)
    lev = calc_safe_leverage(price, sl)
    qty = position_size(price, sl, risk_usd)

    margin_needed = (qty * price) / lev
    balance = get_balance()

    # C: marjin yetmezse kaldıraç yükselt
    adjusted = False
    if margin_needed > balance and balance > 0:
        needed_lev = (qty * price) / balance
        new_lev = min(int(needed_lev) + 1, MAX_LEVERAGE)
        if new_lev > lev:
            lev = new_lev
            margin_needed = (qty * price) / lev
            adjusted = True

    try:
        exchange.set_leverage(lev, symbol, params={"marginMode": "isolated"})
    except Exception as e:
        print("Leverage set warning:", e)

    liq = estimate_liq_price(price, sig, lev)
    stop_before_liq = (sl > liq) if sig == "LONG" else (sl < liq)

    print(f"ENTRY:{round(price,2)} SL:{round(sl,2)} TP:{round(tp,2)} "
          f"LEV:{lev} LIQ:{round(liq,2)} QTY:{qty} "
          f"MARGIN:{round(margin_needed,2)} BAL:{round(balance,2)}")

    if adjusted:
        send_telegram(
            f"⚠️ <b>{name} MARJİN UYARISI — {sig}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Bakiye tam yetmedi, kaldıraç yükseltildi!\n\n"
            f"💰 Bakiye: ${round(balance,2)}\n"
            f"📦 Gereken marjin: ${round(margin_needed,2)}\n"
            f"⚙️ Kaldıraç: {lev}x\n"
            f"💣 Likidasyon: ${round(liq,2)}\n"
            f"🛑 SL: ${round(sl,2)}\n"
            f"⚠️ Stop liq'ten önce mi: {'EVET ✅' if stop_before_liq else 'HAYIR ❌ DİKKAT!'}\n\n"
            f"👁 Kontrol et!"
        )

    if pos:
        if pos["side"] != sig:
            # TERS YÖN → işlem AÇMA, sadece haber ver
            print("TERS SİNYAL — işlem açılmadı")
            send_telegram(
                f"⚠️ <b>{name} TERS SİNYAL</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Açık pozisyon: <b>{pos['side']}</b>\n"
                f"Gelen sinyal: <b>{sig}</b>\n\n"
                f"İşlem AÇILMADI (ters yön).\n"
                f"👁 İstersen manuel kontrol et."
            )
            return  # ters yönde hiçbir şey yapma
        else:
            # AYNI YÖN → pozisyonu büyüt (yeni işlem aç)
            print("AYNI YÖN — pozisyon büyütülüyor")
            open_position(symbol, sig, qty, sl, tp)
            emoji = "🟢" if sig == "LONG" else "🔴"
            send_telegram(
                f"{emoji} <b>{name} EKLEME: {sig}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Mevcut {pos['side']} pozisyonuna eklendi.\n"
                f"💰 Giriş: ${round(price,2)}\n"
                f"🛑 SL: ${round(sl,2)}\n"
                f"🎯 TP: ${round(tp,2)}\n"
                f"⚙️ Kaldıraç: {lev}x\n"
                f"💵 Risk: ${risk_usd}\n"
                f"📦 Miktar: {qty}"
            )
    else:
        # POZİSYON YOK → yeni aç
        open_position(symbol, sig, qty, sl, tp)
        emoji = "🟢" if sig == "LONG" else "🔴"
        send_telegram(
            f"{emoji} <b>{name} İşlem Açıldı: {sig}</b>\n"
            f"💰 Giriş: ${round(price,2)}\n"
            f"🛑 SL: ${round(sl,2)}\n"
            f"🎯 TP: ${round(tp,2)}\n"
            f"⚙️ Kaldıraç: {lev}x\n"
            f"💵 Risk: ${risk_usd}\n"
            f"📦 Miktar: {qty}"
        )

    if sig == "LONG":
        state["last_long_ts"] = candle_ts
    else:
        state["last_short_ts"] = candle_ts
    save_state(state_f, state)

# =========================
# MAIN
# =========================

try:
    print("===== MULTI BOT START =====")
    for coin in COINS:
        try:
            process_coin(coin)
        except Exception as e:
            print(f"{coin['symbol']} hata:", e)
            send_telegram(f"⚠️ <b>{coin['symbol']} hata</b>\n<code>{str(e)[:200]}</code>")
        time.sleep(1)
    print("===== DONE =====")
except Exception as e:
    print("ERROR:", e)
    send_telegram(f"⚠️ <b>BOT HATASI</b>\n<code>{str(e)[:200]}</code>")
