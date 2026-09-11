import os
import sys
import requests

# دریافت توکن ربات از متغیرهای محیطی گیت‌هاب (Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    print("❌ خطای امنیتی: توکن TELEGRAM_BOT_TOKEN در متغیرهای محیطی یا Secrets یافت نشد!")
    sys.exit(1)

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def get_updates(offset=None):
    """دریافت آخرین پیام‌ها و دستورات ارسال شده به ربات"""
    url = f"{BASE_URL}/getUpdates?timeout=20"
    if offset:
        url += f"&offset={offset}"
    try:
        res = requests.get(url, timeout=25).json()
        return res.get("result", [])
    except Exception as e:
        print(f"❌ خطا در دریافت آپدیت‌ها: {e}")
        return []

def send_message(chat_id, text):
    """ارسال پیام متنی به کاربر"""
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=15)
    except Exception as e:
        print(f"❌ خطا در ارسال پیام به {chat_id}: {e}")

def send_file(chat_id, file_path, caption=""):
    """ارسال فایل کانفیگ به کاربر"""
    url = f"{BASE_URL}/sendDocument"
    if not os.path.exists(file_path):
        send_message(chat_id, "❌ در حال حاضر فایلی موجود نیست. لطفاً دقایقی دیگر تلاش کنید.")
        return
    
    try:
        with open(file_path, "rb") as doc:
            requests.post(url, data={
                "chat_id": chat_id,
                "caption": caption or "🚀 خدمت شما! فایل کانفیگ‌های بروز شده:",
                "parse_mode": "HTML"
            }, files={"document": doc}, timeout=30)
    except Exception as e:
        print(f"❌ خطا در ارسال فایل به {chat_id}: {e}")

def handle_updates():
    """بررسی و پاسخ به درخواست‌های کاربران"""
    offset = None
    print("🤖 ربات پاسخگو فعال شد و در حال بررسی درخواست‌هاست...")
    
    updates = get_updates(offset)
    if not updates:
        print("ℹ️ هیچ درخواست جدیدی برای پاسخگویی وجود ندارد.")
        return

    for update in updates:
        offset = update["update_id"] + 1
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()

        if not chat_id:
            continue

        file_path = "subs/subscription_part1.txt"

        if text in ["/start", "/get_all"]:
            caption = (
                "🚀 <b>لیست جامع کانفیگ‌های پرسرعت</b>\n\n"
                "📦 شامل انواع پروتکل‌های VLESS، VMESS، Trojan و...\n"
                "⚡️ تست شده با پینگ پایین و متصل به سرورهای باکیفیت"
            )
            send_file(chat_id, file_path, caption)

        elif text == "/vless":
            send_file(chat_id, file_path, "⚡️ <b>کانفیگ‌های اختصاصی VLESS</b>\nاز فایل زیر برای اتصال استفاده کنید:")

        elif text == "/vmess":
            send_file(chat_id, file_path, "🛡 <b>کانفیگ‌های اختصاصی VMESS</b>\nاز فایل زیر برای اتصال استفاده کنید:")

        elif text == "/trojan":
            send_file(chat_id, file_path, "🔒 <b>کانفیگ‌های اختصاصی Trojan</b>\nاز فایل زیر برای اتصال استفاده کنید:")

        elif text == "/shadowsocks":
            send_file(chat_id, file_path, "✈️ <b>کانفیگ‌های اختصاصی Shadowsocks</b>\nاز فایل زیر برای اتصال استفاده کنید:")

        elif text == "/hysteria":
            send_file(chat_id, file_path, "🚀 <b>کانفیگ‌های اختصاصی Hysteria2</b>\nاز فایل زیر برای اتصال استفاده کنید:")

        elif text == "/help":
            help_text = (
                "❓ <b>راهنمای استفاده از ربات:</b>\n\n"
                "🔹 برای دریافت کامل‌ترین لیست کانفیگ‌ها دستور /start یا /get_all را بزنید.\n"
                "🔹 برای دریافت پروتکل‌های خاص می‌توانید از منوی دستورات ربات پروتکل موردنظر را انتخاب کنید.\n\n"
                "📢 کانال رسمی ما:\n"
                "https://t.me/Goodbaye_filtering"
            )
            send_message(chat_id, help_text)

if __name__ == "__main__":
    handle_updates()
