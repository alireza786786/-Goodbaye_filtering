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

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

def send_file(chat_id, file_path, caption=""):
    url = f"{BASE_URL}/sendDocument"
    if not os.path.exists(file_path):
        send_message(chat_id, "❌ در حال حاضر فایلی موجود نیست. لطفاً چند دقیقه دیگر تلاش کنید.")
        return
    with open(file_path, "rb") as doc:
        requests.post(url, data={
            "chat_id": chat_id,
            "caption": caption or "🚀 خدمت شما! فایل کانفیگ‌های بروز شده:"
        }, files={"document": doc})

def handle_updates():
    offset = None
    print("🤖 Robot responder started...")
    
    updates = get_updates(offset)
    for update in updates:
        offset = update["update_id"] + 1
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()

        if not chat_id:
            continue

        if text in ["/start", "/get_all"]:
            send_file(chat_id, "subs/subscription_part1.txt", "🚀 فایل کامل کانفیگ‌های تست‌شده و پرسرعت")
            
        elif text == "/help":
            help_text = (
                "❓ <b>راهنمای استفاده از ربات:</b>\n\n"
                "🔹 برای دریافت فایل کامل کانفیگ‌ها از دستور /start یا /get_all استفاده کنید.\n"
                "🔹 جهت دریافت پروتکل‌های خاص می‌توانید از منوی دستورات ربات پروتکل موردنظر خود را انتخاب کنید."
            )
            send_message(chat_id, help_text)

        elif text in ["/vless", "/vmess", "/trojan", "/shadowsocks", "/hysteria"]:
            # ارسال فایل اصلی جهت پشتیبانی از تمام پروتکل‌ها
            send_file(chat_id, "subs/subscription_part1.txt", f"⚡️ لیست کانفیگ‌های بخش {text.replace('/', '').upper()}")

if __name__ == "__main__":
    handle_updates()
