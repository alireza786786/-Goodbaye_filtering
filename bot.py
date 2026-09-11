import os
import sys
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    print("❌ خطای امنیتی: توکن ربات یافت نشد!")
    sys.exit(1)

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates?timeout=20"
    if offset:
        url += f"&offset={offset}"
    try:
        res = requests.get(url, timeout=25).json()
        return res.get("result", [])
    except Exception as e:
        print(f"❌ خطا در دریافت پیام‌ها: {e}")
        return []

def send_message(chat_id, text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=15)
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")

def load_and_categorize_configs():
    """خواندن فایل‌های تولید شده و تفکیک کانفیگ‌ها بر اساس پروتکل"""
    file_path = "subs/plain.txt"
    categorized = {
        "vless": [],
        "vmess": [],
        "trojan": [],
        "ss": [],
        "hysteria": []
    }
    
    if not os.path.exists(file_path):
        # اگر فایل plain مستقیم نبود، فایل‌های پارت را باز می‌کند
        file_path = "subs/subscription_part1.txt"

    if not os.path.exists(file_path):
        return categorized

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith("vless://"):
            categorized["vless"].append(line)
        elif line.startswith("vmess://"):
            categorized["vmess"].append(line)
        elif line.startswith("trojan://"):
            categorized["trojan"].append(line)
        elif line.startswith("ss://"):
            categorized["ss"].append(line)
        elif line.startswith("hy2://") or line.startswith("hysteria2://"):
            categorized["hysteria"].append(line)

    return categorized

def handle_updates():
    offset = None
    print("🤖 ربات تفکیک‌کننده کانفیگ فعال شد...")

    updates = get_updates(offset)
    if not updates:
        print("ℹ️ پیام جدیدی یافت نشد.")
        return

    # بارگذاری و تفکیک کانفیگ‌ها
    configs = load_and_categorize_configs()

    for update in updates:
        offset = update["update_id"] + 1
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip().lower()

        if not chat_id:
            continue

        if text == "/start":
            msg = (
                "👋 <b>به ربات دریافت کانفیگ خوش آمدید!</b>\n\n"
                "برای دریافت کانفیگ‌های تفکیک‌شده و آماده‌ی کپی، یکی از دستورات زیر را بفرستید یا از منو انتخاب کنید:\n\n"
                "⚡️ /vless - دریافت کانفیگ‌های VLESS\n"
                "🛡 /vmess - دریافت کانفیگ‌های VMESS\n"
                "🔒 /trojan - دریافت کانفیگ‌های Trojan\n"
                "✈️ /shadowsocks - دریافت کانفیگ‌های Shadowsocks\n"
                "🚀 /hysteria - دریافت کانفیگ‌های Hysteria2\n\n"
                "📦 /get_all - دریافت همه کانفیگ‌ها"
            )
            send_message(chat_id, msg)

        elif text in ["/vless", "/vmess", "/trojan", "/shadowsocks", "/hysteria"]:
            proto_key = text.replace("/", "")
            if proto_key == "shadowsocks":
                proto_key = "ss"

            selected = configs.get(proto_key, [])
            if not selected:
                send_message(chat_id, f"❌ در حال حاضر کانفیگی برای بخش {text.upper()} موجود نیست.")
            else:
                # جدا کردن ۵ کانفیگ برتر همان پروتکل برای ارسال متنی (جهت کپی راحت)
                top_configs = selected[:5]
                formatted_list = "\n\n".join([f"<code>{c}</code>" for c in top_configs])
                
                reply = (
                    f"🚀 <b>کانفیگ‌های تفکیک‌شده {text.replace('/', '').upper()}:</b>\n\n"
                    f"{formatted_list}\n\n"
                    f"👇 روی کدها بزنید تا کپی شوند."
                )
                send_message(chat_id, reply)

        elif text == "/get_all":
            all_list = []
            for k in configs:
                all_list.extend(configs[k][:2]) # ۲ تا از هر پروتکل
            
            if not all_list:
                send_message(chat_id, "❌ کانفیگی یافت نشد.")
            else:
                formatted_list = "\n\n".join([f"<code>{c}</code>" for c in all_list])
                reply = (
                    f"📦 <b>مجموعه کانفیگ‌های برتر (تست‌شده):</b>\n\n"
                    f"{formatted_list}\n\n"
                    f"👇 روی کدها بزنید تا کپی شوند."
                )
                send_message(chat_id, reply)

if __name__ == "__main__":
    handle_updates()
