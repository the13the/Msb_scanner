import os
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")


def send_test():
    print("===== TELEGRAM DEBUG START =====")

    print("TOKEN OK:", bool(TELEGRAM_TOKEN))
    print("CHAT_ID OK:", bool(CHAT_ID))

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[ERROR] ENV eksik!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": "🧪 TELEGRAM TEST MESAJI - DEBUG CHECK"
    }

    try:
        r = requests.post(url, data=payload, timeout=10)

        print("[STATUS CODE]", r.status_code)
        print("[RESPONSE]", r.text)

        if r.status_code == 200:
            print("✅ TELEGRAM ÇALIŞIYOR")
        else:
            print("❌ TELEGRAM HATA VERDİ")

    except Exception as e:
        print("❌ EXCEPTION:", e)


if __name__ == "__main__":
    send_test()
