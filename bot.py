import os
import requests

TELEGRAM_BOT_TOKEN = "8991715334:AAGx1qfFC0aZm1dmhrfpjV8Cxh85b6Th66s"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates?timeout=30"
    if offset:
        url += f"&offset={offset}"
    try:
        res = requests.get(url, timeout=35).json()
        return res.get("result", [])
    except Exception:
        return []

def send_file(chat_id, file_path):
    url = f"{BASE_URL}/sendDocument"
    if not os.path.exists(file_path):
        requests.post(f"{BASE_URL}/sendMessage", data={
            "chat_id": chat_id,
            "text": "❌ در حال حاضر فایلی موجود نیست. لطفاً بعداً تلاش کنید."
        })
        return
    with open(file_path, "rb") as doc:
        requests.post(url, data={
            "chat_id": chat_id,
            "caption": "🚀 خدمت شما! فایل کانفیگ‌های بروز شده:"
        }, files={"document": doc})

def handle_updates():
    offset = None
    print("🤖 Robot responder started...")
    
    # ربات برای مدت محدودی روی اکشن اجرا می‌شود تا پیام‌ها را پاسخ دهد
    for _ in range(10):  
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")

            if text == "/start":
                file_to_send = "subs/subscription_part1.txt"
                send_file(chat_id, file_to_send)
                
if __name__ == "__main__":
    handle_updates()
