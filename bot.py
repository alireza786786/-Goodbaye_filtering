import os
import sys
import socket
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# دریافت آیدی کانال به صورت امن از Secrets
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
    print("❌ خطای امنیتی: TELEGRAM_BOT_TOKEN یا CHANNEL_ID در متغیرهای محیطی یافت نشد!")
    sys.exit(1)

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ---------------------------------------------------------
# ۱. توابع ارتباط با تلگرام
# ---------------------------------------------------------
def get_updates(offset=None):
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
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=15)
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")

# ---------------------------------------------------------
# ۲. دانلود آخرین فایل ارسالی از کانال
# ---------------------------------------------------------
def fetch_configs_from_channel():
    """خوانش آخرین فایل ارسال‌شده در کانال تلگرام"""
    print("📥 در حال بررسی کانال جهت دریافت آخرین فایل...")
    url = f"{BASE_URL}/getUpdates"
    try:
        res = requests.get(url, timeout=20).json()
        updates = res.get("result", [])
        
        file_id = None
        for upd in reversed(updates):
            post = upd.get("channel_post", {})
            if str(post.get("chat", {}).get("id")) == str(CHANNEL_ID):
                doc = post.get("document")
                if doc:
                    file_id = doc.get("file_id")
                    break

        if not file_id:
            print("⚠️ فایلی در پست‌های اخیر کانال یافت نشد. از فایل محلی پشتیبان استفاده می‌شود.")
            return read_local_fallback()

        file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
        file_path = file_info.get("result", {}).get("file_path")
        
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        content = requests.get(download_url, timeout=30).text
        return content.splitlines()

    except Exception as e:
        print(f"❌ خطا در خواندن کانال: {e}")
        return read_local_fallback()

def read_local_fallback():
    file_path = "subs/plain.txt"
    if not os.path.exists(file_path):
        file_path = "subs/subscription_part1.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.readlines()
    return []

# ---------------------------------------------------------
# ۳. پارسر و تست پینگ TCP
# ---------------------------------------------------------
def parse_host_port(config):
    """استخراج IP/Domain و Port از انواع کانفیگ‌ها"""
    try:
        if config.startswith("vless://") or config.startswith("vmess://") or config.startswith("trojan://"):
            parts = config.split("@")
            if len(parts) > 1:
                host_port = parts[1].split("/")[0].split("?")[0]
                host, port = host_port.split(":")
                return host, int(port)
        elif config.startswith("ss://"):
            raw = config.replace("ss://", "").split("#")[0]
            if "@" in raw:
                server_info = raw.split("@")[1]
                host, port = server_info.split(":")
                return host, int(port)
    except Exception:
        pass
    return None, None

def test_tcp_ping(host, port, timeout=2):
    """تست زنده بودن سرور"""
    if not host or not port:
        return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

# ---------------------------------------------------------
# ۴. تفکیک و فیلتر ۱۰ کانفیگ سالم
# ---------------------------------------------------------
def process_and_categorize(raw_lines):
    categorized = {
        "vless": [],
        "vmess": [],
        "trojan": [],
        "ss": [],
        "hysteria": []
    }

    print("⚡️ در حال تست پینگ و تفکیک کانفیگ‌های دریافت‌شده...")
    for line in raw_lines:
        config = line.strip()
        if not config:
            continue

        proto = None
        if config.startswith("vless://"): proto = "vless"
        elif config.startswith("vmess://"): proto = "vmess"
        elif config.startswith("trojan://"): proto = "trojan"
        elif config.startswith("ss://"): proto = "ss"
        elif config.startswith("hy2://") or config.startswith("hysteria2://"): proto = "hysteria"

        if proto and len(categorized[proto]) < 10:
            host, port = parse_host_port(config)
            if not host or test_tcp_ping(host, port):
                categorized[proto].append(config)

    return categorized

# ---------------------------------------------------------
# ۵. پاسخگویی ربات به کاربران
# ---------------------------------------------------------
def handle_updates():
    offset = None
    print("🤖 ربات هوشمند تفکیک و تست کانفیگ فعال شد...")

    updates = get_updates(offset)
    if not updates:
        print("ℹ️ پیام جدیدی از کاربران دریافت نشده است.")
        return

    raw_configs = fetch_configs_from_channel()
    configs = process_and_categorize(raw_configs)

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
                "کانفیگ‌ها مستقیماً از کانال استخراج، **تست آنلاین** و تفکیک شده‌اند.\n\n"
                "برای دریافت کانفیگ آماده‌ی کپی، یکی از گزینه‌های زیر را انتخاب کنید:\n\n"
                "⚡️ /vless - دریافت ۱۰ کانفیگ VLESS\n"
                "🛡 /vmess - دریافت ۱۰ کانفیگ VMESS\n"
                "🔒 /trojan - دریافت ۱۰ کانفیگ Trojan\n"
                "✈️ /shadowsocks - دریافت ۱۰ کانفیگ Shadowsocks\n"
                "🚀 /hysteria - دریافت ۱۰ کانفیگ Hysteria2\n\n"
                "📦 /get_all - دریافت ترکیبی از برترین‌ها"
            )
            send_message(chat_id, msg)

        elif text in ["/vless", "/vmess", "/trojan", "/shadowsocks", "/hysteria"]:
            proto_key = text.replace("/", "")
            if proto_key == "shadowsocks": proto_key = "ss"

            selected = configs.get(proto_key, [])
            if not selected:
                send_message(chat_id, f"❌ در حال حاضر کانفیگ سالمی برای بخش {text.upper()} یافت نشد.")
            else:
                formatted_list = "\n\n".join([f"<code>{c}</code>" for c in selected])
                reply = (
                    f"🚀 <b>۱۰ کانفیگ تست‌شده و پرسرعت {text.replace('/', '').upper()}:</b>\n\n"
                    f"{formatted_list}\n\n"
                    f"👇 روی هر کد بزنید تا کپی شود."
                )
                send_message(chat_id, reply)

        elif text == "/get_all":
            all_list = []
            for k in configs:
                all_list.extend(configs[k][:2])
            
            if not all_list:
                send_message(chat_id, "❌ کانفیگ سالمی یافت نشد.")
            else:
                formatted_list = "\n\n".join([f"<code>{c}</code>" for c in all_list])
                reply = (
                    f"📦 <b>مجموعه برترین کانفیگ‌های فعال:</b>\n\n"
                    f"{formatted_list}\n\n"
                    f"👇 روی هر کد بزنید تا کپی شود."
                )
                send_message(chat_id, reply)

if __name__ == "__main__":
    handle_updates()
