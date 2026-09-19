import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
import json
import os
import re
import socket
import ssl
import time
from urllib.parse import parse_qs, quote, urlparse
import requests

# ---------------------------------------------------------
# دریافت اطلاعات محرمانه از GitHub Secrets
# ---------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
SOURCES_RAW = os.environ.get("SOURCES_JSON", "{}").strip()

try:
    SOURCES = json.loads(SOURCES_RAW)
except Exception as e:
    print(f"❌ خطا در خواندن SOURCES_JSON: {e}")
    SOURCES = {}

SAFE_TLS_PORTS = {443, 8443, 2053, 2083, 2087, 2096, 2052, 8080, 8880}
TIMEOUT = 1.8
MAX_WORKERS = 80

def get_flag(country_code):
    if country_code and len(country_code) == 2:
        return "".join(chr(127397 + ord(x.upper())) for x in country_code)
    return "🌐"

def fetch_geo_batch(ip_list):
    geo = {}
    if not ip_list:
        return geo
    for i in range(0, len(ip_list), 100):
        batch = ip_list[i:i+100]
        try:
            r = requests.post("http://ip-api.com/batch?fields=query,status,country,city,countryCode", json=batch, timeout=10)
            if r.status_code == 200:
                for item in r.json():
                    if item.get("status") == "success":
                        geo[item["query"]] = {
                            "country": item.get("country", "Unknown"),
                            "city": item.get("city", "Unknown"),
                            "flag": get_flag(item.get("countryCode", ""))
                        }
        except Exception:
            pass
    return geo

def stress_test_config(host, port, sni, is_tls):
    # شات اول پینگ
    t0 = time.time()
    try:
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.settimeout(TIMEOUT)
        s1.connect((host, int(port)))
        s1.close()
        p1 = (time.time() - t0) * 1000
    except Exception:
        return None, None, False

    time.sleep(0.15)

    # شات دوم پینگ
    t1 = time.time()
    try:
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.settimeout(TIMEOUT + 1.0)
        s2.connect((host, int(port)))
        p2 = (time.time() - t1) * 1000
    except Exception:
        return None, None, False

    jitter = abs(p2 - p1)
    avg_ping = (p1 + p2) / 2.0

    if jitter > 70.0 or avg_ping > 480.0:
        s2.close()
        return None, None, False

    tls_passed = False
    if is_tls and sni:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            with ctx.wrap_socket(s2, server_hostname=sni) as ss:
                ss.do_handshake()
                dummy_req = f"GET / HTTP/1.1\r\nHost: {sni}\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n"
                ss.sendall(dummy_req.encode('utf-8'))
                res = ss.recv(512)
                if res:
                    tls_passed = True
        except Exception:
            tls_passed = False
        finally:
            try: s2.close()
            except Exception: pass
    else:
        s2.close()
        tls_passed = True

    return round(avg_ping, 1), round(jitter, 1), tls_passed

def detect_arch_bonus(net, sec, fl, raw_link, port):
    bonus = 0
    if port in [443, 8443, 2053]:
        bonus += 100

    if net in ["xhttp", "xray"]:
        return "XHTTP-Elite", bonus + 400
    if sec == "reality" and "xtls-rprx-vision" in fl:
        if "xPaddingBytes" in raw_link:
            bonus += 50
        return "Reality-Vision", bonus + 350
    if sec == "reality" and net == "grpc":
        return "Reality-gRPC", bonus + 300
    if sec == "reality":
        return "Reality", bonus + 250
    if net == "hysteria2" or "hysteria2://" in raw_link or "hy2://" in raw_link:
        return "Hysteria2", bonus + 380
    return "TLS-Tunnel", bonus + 150

def parse_and_test_config(raw_url):
    raw_url = raw_url.strip()
    
    # --- پردازش اختصاصی VMess (Base64 JSON) ---
    if raw_url.startswith("vmess://"):
        try:
            b64_str = raw_url[8:].split('#')[0].strip()
            padded = b64_str + "=" * ((4 - len(b64_str) % 4) % 4)
            data_json = json.loads(base64.b64decode(padded).decode('utf-8', errors='ignore'))
            
            host = data_json.get("add", "").strip()
            port = int(data_json.get("port", 0))
            if not host or not port:
                return None

            try:
                ip = socket.gethostbyname(host)
            except Exception:
                ip = host

            net = data_json.get("net", "").lower()
            sec = data_json.get("tls", "").lower()
            sni = data_json.get("sni", "") or data_json.get("host", "") or host
            is_tls = sec in ["tls", "reality"]

            ping, jitter, tls_passed = stress_test_config(ip, port, sni, is_tls)
            if ping is not None and tls_passed:
                arch, bonus = detect_arch_bonus(net, sec, "", raw_url, port)
                power_score = (100000.0 / ping) - (jitter * 2.0) + bonus
                return {
                    "proto": "vmess",
                    "json_data": data_json,
                    "ip": ip,
                    "port": port,
                    "ping": ping,
                    "jitter": jitter,
                    "arch": arch,
                    "score": round(power_score, 2)
                }
        except Exception:
            return None

    # --- پردازش سایر پروتکل‌ها (VLESS, Trojan, SS, Socks, Hy2, Tuic) ---
    try:
        parsed = urlparse(raw_url)
        scheme = parsed.scheme.lower()
        if scheme not in ["vless", "trojan", "hysteria2", "hy2", "tuic", "ss", "socks", "socks5"]:
            return None

        query = parse_qs(parsed.query)
        host = parsed.hostname or ""
        port = int(parsed.port or 0)
        if not host or not port:
            return None

        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = host

        sec = query.get("security", [""])[0].lower()
        net = query.get("type", [""])[0].lower() or scheme
        fl = query.get("flow", [""])[0].lower()
        sni = query.get("sni", [""])[0] or host

        is_tls = sec in ["reality", "tls"] or scheme in ["hysteria2", "hy2", "trojan"]
        
        ping, jitter, tls_passed = stress_test_config(ip, port, sni, is_tls)
        if ping is not None and tls_passed:
            arch, bonus = detect_arch_bonus(net, sec, fl, raw_url, port)
            power_score = (100000.0 / ping) - (jitter * 2.0) + bonus
            base_url = raw_url.split("#")[0]
            return {
                "proto": scheme,
                "base_url": base_url,
                "ip": ip,
                "port": port,
                "ping": ping,
                "jitter": jitter,
                "arch": arch,
                "score": round(power_score, 2)
            }
    except Exception:
        pass
    return None

def test_telegram_proxy(proxy_url):
    try:
        clean_url = proxy_url.strip()
        server, port = None, None
        if "server=" in clean_url and "port=" in clean_url:
            parsed = urlparse(clean_url)
            params = parse_qs(parsed.query)
            server = params.get("server", [""])[0]
            port = int(params.get("port", [0])[0])
        elif clean_url.startswith("tg://proxy?") or clean_url.startswith("https://t.me/proxy?"):
            parsed = urlparse(clean_url)
            params = parse_qs(parsed.query)
            server = params.get("server", [""])[0]
            port = int(params.get("port", [0])[0])

        if server and port:
            t0 = time.time()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            s.connect((server, port))
            s.close()
            latency = round((time.time() - t0) * 1000, 1)
            return {"url": clean_url, "server": server, "latency": latency}
    except Exception:
        pass
    return None

def fetch_urls_from_source(url):
    configs = []
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return configs
        content = r.text.strip()
        
        # بررسی بستر Base64 کلی
        if not any(p in content for p in ["vless://", "vmess://", "trojan://", "tg://"]):
            try:
                padded = content + "=" * ((4 - len(content) % 4) % 4)
                decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
                if len(decoded) > 20:
                    content = decoded
            except Exception:
                pass

        lines = content.splitlines()
        valid_prefixes = ["vless://", "vmess://", "trojan://", "hysteria2://", "hy2://", "tuic://", "ss://", "socks://", "socks5://", "tg://proxy", "https://t.me/proxy"]
        for line in lines:
            line = line.strip()
            if any(line.startswith(prefix) for prefix in valid_prefixes):
                configs.append(line)
    except Exception:
        pass
    return configs

def process_guard_group(group_key, url_list):
    print(f"\n🔄 در حال پردازش {group_key} با {len(url_list)} منبع...")
    raw_configs = []
    for u in url_list:
        raw_configs.extend(fetch_urls_from_source(u))
    
    raw_configs = list(set(raw_configs))
    print(f"📦 تعداد کل کاندیدها در {group_key}: {len(raw_configs)}")

    if group_key == "by8":
        valid_proxies = []
        with ThreadPoolExecutor(max_workers=50) as ex:
            futs = [ex.submit(test_telegram_proxy, p) for p in raw_configs]
            for f in as_completed(futs):
                res = f.result()
                if res:
                    valid_proxies.append(res)
        valid_proxies.sort(key=lambda x: x["latency"])
        return [p["url"] for p in valid_proxies]

    tested_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(parse_and_test_config, cfg) for cfg in raw_configs]
        for f in as_completed(futs):
            res = f.result()
            if res:
                tested_results.append(res)

    tested_results.sort(key=lambda x: x["score"], reverse=True)

    unique_map = {}
    for item in tested_results:
        key = (item["ip"], item["port"])
        if key not in unique_map:
            unique_map[key] = item

    final_list = list(unique_map.values())
    geo_data = fetch_geo_batch(list({x["ip"] for x in final_list}))

    output_lines = []
    for item in final_list:
        geo = geo_data.get(item["ip"], {"country": "Unknown", "city": "Unknown", "flag": "🌐"})
        tag_str = f"👉🆔@Goodbaye_filtering📡{geo['flag']}®️{geo['country']}©️{geo['city']}🅿️ping:{item['ping']}ms~±{item['jitter']}ms⚡️{item['arch']}"
        
        # اعمال برچسب بر اساس نوع پروتکل
        if item["proto"] == "vmess":
            v_json = item["json_data"]
            v_json["ps"] = tag_str  # تزریق مستقیم به پارامتر ps
            encoded_vmess = base64.b64encode(json.dumps(v_json, ensure_ascii=False).encode('utf-8')).decode('utf-8')
            output_lines.append(f"vmess://{encoded_vmess}")
        else:
            output_lines.append(f"{item['base_url']}#{quote(tag_str)}")

    return output_lines

def send_telegram_file(file_path, group_name, count):
    if not BOT_TOKEN or not CHANNEL_ID:
        return
    tehran_tz = timezone(timedelta(hours=3, minutes=30))
    now_str = datetime.now(tehran_tz).strftime("%Y-%m-%d | %H:%M:%S")
    
    caption = f"""💎 بروزرسانی خودکار سابسکرایپ {group_name.upper()}

📊 تعداد کانفیگ‌های الماس: {count}
🕒 زمان بروزرسانی: {now_str} (تهران)
🛡 وضعیت: عبور داده شده از تست ۳ مرحله‌ای DPI و Jitter

✨ کانال: https://t.me/Goodbaye_filtering
💬 گروه: https://t.me/CONFIG_V2RAY_VIP"""

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        with open(file_path, "rb") as f:
            requests.post(url, data={"chat_id": CHANNEL_ID, "caption": caption}, files={"document": f}, timeout=30)
    except Exception as e:
        print(f"❌ خطای ارسال به تلگرام برای {group_name}: {e}")

def main():
    if not SOURCES:
        print("❌ هیچ منبعی در SOURCES_JSON تعریف نشده است.")
        return

    groups = ["guard1", "guard2", "guard3", "guard4", "guard5", "guard6", "guard7", "by8"]
    
    for idx, g_key in enumerate(groups, 1):
        url_list = SOURCES.get(g_key, [])
        if not url_list:
            print(f"⚠️ گروه {g_key} خالی است.")
            continue

        result_lines = process_guard_group(g_key, url_list)
        
        txt_filename = f"sub{idx}.txt"
        b64_filename = f"sub{idx}_b64.txt"
        
        content = "\n".join(result_lines)
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(content)

        b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        with open(b64_filename, "w", encoding="utf-8") as f:
            f.write(b64_content)

        print(f"✅ فایل‌های {txt_filename} و {b64_filename} با {len(result_lines)} آیتم ذخیره شدند.")
        
        send_telegram_file(txt_filename, f"Guard-{idx}" if idx <= 7 else "Telegram-Proxies", len(result_lines))

if __name__ == "__main__":
    main()
