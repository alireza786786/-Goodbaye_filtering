#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Telegram Proxy Collector v2.2
جمع‌آوری، تست سرعت (پینگ واقعی)، مرتب‌سازی، ارسال فایل و ۳ پروکسی برتر با دکمه شیشه‌ای.
(منابع به صورت امن از SOURCES_JSON دریافت می‌شوند)
"""

import asyncio
import os
import re
import sys
import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from pathlib import Path

import aiohttp

# ==================== تنظیم Logging ====================
def setup_logging():
    """تنظیم سیستم logging جامع"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler('proxy_collector.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==================== تنظیمات و دریافت امن منابع ====================
OUTPUT_FILE = "TELEGRAM_PROXY_SUB_TXT"
CHANNEL_LINK = "https://t.me/Goodbaye_filtering"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()

def load_sources_from_env() -> List[str]:
    """دریافت امن منابع پروکسی از سکرت SOURCES_JSON"""
    raw_json = os.environ.get("SOURCES_JSON", "").strip()
    if not raw_json:
        logger.error("❌ متغیر SOURCES_JSON یافت نشد!")
        return []
    try:
        data = json.loads(raw_json)
        # کلید by8 حاوی منابع پروکسی تلگرام است
        sources = data.get("by8", [])
        logger.info(f"🔑 تعداد {len(sources)} منبع پروکسی از SOURCES_JSON استخراج شد.")
        return sources
    except Exception as e:
        logger.error(f"❌ خطا در خواندن SOURCES_JSON: {e}")
        return []

SOURCES = load_sources_from_env()

# تنظیمات شبکه و Timeout
FETCH_TIMEOUT = 15.0
TCP_TIMEOUT = 5.0
MAX_CONCURRENT_TESTS = 40
MAX_RETRIES = 3
RETRY_DELAY = 2.0

PROXY_RE = re.compile(r"(?:https?://t\.me|tg://)/?(?:proxy)?\?[^\s'\"<>]+")


# ==================== Validation ====================
def validate_environment():
    """بررسی صحت متغیرهای محیطی"""
    logger.info("🔍 بررسی متغیرهای محیطی...")
    
    if not BOT_TOKEN:
        logger.warning("⚠️ BOT_TOKEN تنظیم نشده است. پیام‌ها به تلگرام ارسال نخواهند شد.")
        return False
    
    if not CHAT_ID:
        logger.warning("⚠️ CHAT_ID تنظیم نشده است. پیام‌ها به تلگرام ارسال نخواهند شد.")
        return False
    
    logger.info("✅ متغیرهای محیطی بررسی شدند.")
    return True


# ==================== Data Classes ====================
@dataclass
class ProxyLink:
    """کلاس برای نمایندگی پروکسی"""
    server: str
    port: int
    secret: str
    raw: str
    latency: float = 999.0  # سرعت پاسخ‌دهی (پینگ) به میلی‌ثانیه

    def __hash__(self):
        return hash((self.server, self.port, self.secret))

    def __eq__(self, other):
        if not isinstance(other, ProxyLink):
            return False
        return (self.server, self.port, self.secret) == (other.server, other.port, other.secret)


# ==================== Parsing ====================
def parse_proxy_line(line: str) -> Optional[ProxyLink]:
    """تجزیه خط پروکسی و استخراج اطلاعات"""
    line = line.strip()
    if not line:
        return None
    
    try:
        m = PROXY_RE.search(line)
        if not m:
            return None
        
        url = m.group(0)
        normalized = url if url.startswith("http") else "https://t.me/proxy" + url[url.index("?"):]
        parsed = urlparse(normalized)
        qs = parse_qs(parsed.query)
        
        server = (qs.get("server", [""])[0] or "").strip().rstrip(".").lower()
        port_raw = (qs.get("port", [""])[0] or "").strip()
        secret = (qs.get("secret", [""])[0] or "").strip()
        
        if not server or not port_raw.isdigit() or not secret:
            return None
        
        port = int(port_raw)
        if not (0 < port < 65536):
            return None
        
        clean_url = f"https://t.me/proxy?server={server}&port={port}&secret={secret}"
        return ProxyLink(server=server, port=port, secret=secret, raw=clean_url)
    
    except Exception as e:
        logger.debug(f"خطا در تجزیه خط: {line[:50]}... - {e}")
        return None


# ==================== Fetching with Retry ====================
async def fetch_source(session: aiohttp.ClientSession, url: str, retries: int = MAX_RETRIES) -> List[str]:
    """دریافت منبع با retry mechanism برای شبکه‌های ناپایدار"""
    for attempt in range(retries):
        try:
            logger.info(f"📥 درحال دریافت منبع (تلاش {attempt + 1}/{retries})...")
            
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT),
                ssl=False,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            ) as r:
                if r.status != 200:
                    logger.warning(f"⚠️ وضعیت HTTP {r.status}")
                    if attempt < retries - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    continue
                
                text = await r.text(errors="ignore")
                lines = text.splitlines()
                logger.info(f"✅ {len(lines)} خط دریافت شد")
                return lines
        
        except asyncio.TimeoutError:
            logger.warning(f"⏱ Timeout (تلاش {attempt + 1}/{retries})")
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)
        except Exception as e:
            logger.warning(f"❌ خطا در دریافت: {e} (تلاش {attempt + 1}/{retries})")
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)
    
    return []


async def collect_all() -> List[ProxyLink]:
    """جمع‌آوری تمام پروکسی‌ها از منابع"""
    logger.info("=" * 60)
    logger.info("🚀 شروع جمع‌آوری پروکسی‌ها")
    logger.info("=" * 60)
    
    if not SOURCES:
        logger.error("❌ هیچ منبعی برای خواندن وجود ندارد!")
        return []

    connector = aiohttp.TCPConnector(
        limit_per_host=5,
        limit=100,
        ttl_dns_cache=300,
        ssl=False
    )
    
    async with aiohttp.ClientSession(connector=connector) as session:
        all_lines = await asyncio.gather(
            *[fetch_source(session, u) for u in SOURCES],
            return_exceptions=True
        )

    seen: Set[Tuple[str, int, str]] = set()
    proxies: List[ProxyLink] = []
    
    for i, lines in enumerate(all_lines):
        if isinstance(lines, Exception):
            logger.error(f"❌ خطا در دریافت منبع {i+1}: {lines}")
            continue
        
        for line in lines:
            p = parse_proxy_line(line)
            if not p:
                continue
            
            key = (p.server, p.port, p.secret)
            if key in seen:
                continue
            
            seen.add(key)
            proxies.append(p)
    
    logger.info(f"✅ {len(proxies)} پروکسی یکتا جمع‌آوری شد")
    return proxies


# ==================== Testing ====================
async def measure_latency(p: ProxyLink, sem: asyncio.Semaphore) -> Optional[ProxyLink]:
    """تست TCP و محاسبه latency دقیق"""
    async with sem:
        start_time = asyncio.get_event_loop().time()
        writer = None
        try:
            fut = asyncio.open_connection(p.server, p.port)
            _, writer = await asyncio.wait_for(fut, timeout=TCP_TIMEOUT)
            end_time = asyncio.get_event_loop().time()
            p.latency = round((end_time - start_time) * 1000, 2)
            logger.debug(f"✅ {p.server}:{p.port} - Latency: {p.latency}ms")
            return p
        
        except asyncio.TimeoutError:
            logger.debug(f"⏱ {p.server}:{p.port} - Timeout")
            return None
        except Exception as e:
            logger.debug(f"❌ {p.server}:{p.port} - {type(e).__name__}: {e}")
            return None
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass


async def filter_and_sort_alive(proxies: List[ProxyLink]) -> List[ProxyLink]:
    """فیلتر پروکسی‌های سالم و مرتب‌سازی بر اساس سرعت"""
    logger.info(f"🧪 شروع تست {len(proxies)} پروکسی...")
    
    sem = asyncio.Semaphore(MAX_CONCURRENT_TESTS)
    results = await asyncio.gather(*[measure_latency(p, sem) for p in proxies])
    
    alive_proxies = [p for p in results if p is not None]
    alive_proxies.sort(key=lambda x: x.latency)
    
    logger.info(f"✅ {len(alive_proxies)} پروکسی زنده تأیید شد")
    
    if alive_proxies:
        logger.info(f"🏆 سریع‌ترین پروکسی: {alive_proxies[0].server} (Latency: {alive_proxies[0].latency}ms)")
    
    return alive_proxies


# ==================== File Operations ====================
async def save_proxies_to_file(file_path: str, proxies: List[ProxyLink]) -> bool:
    """ذخیره پروکسی‌ها در فایل"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(p.raw for p in proxies))
        
        logger.info(f"💾 {len(proxies)} پروکسی در فایل «{file_path}» ذخیره شدند")
        return True
    
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره فایل: {e}")
        return False


# ==================== Telegram Sending ====================
async def send_to_telegram(file_path: str, proxies: List[ProxyLink]) -> None:
    """ارسال پروکسی‌ها و اطلاعات به تلگرام"""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("⚠️ BOT_TOKEN یا CHAT_ID تنظیم نشده است. پیام ارسال نخواهد شد.")
        return

    if not Path(file_path).exists():
        logger.error(f"❌ فایل «{file_path}» وجود ندارد.")
        return

    count = len(proxies)
    logger.info(f"📤 درحال ارسال {count} پروکسی به تلگرام...")
    
    caption = (
        "📡 <b>پروکسی‌های MTProto تلگرام</b>\n\n"
        f"📦 تعداد کل پروکسی‌های زنده: <b>{count}</b>\n"
        f"⏱ تاریخ به‌روزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "🔄 هر ۴ ساعت یک‌بار به‌روزرسانی می‌شود\n\n"
        f"✨ منبع: {CHANNEL_LINK}"
    )

    url_doc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # ۱. ارسال فایل
            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", CHAT_ID)
                data.add_field("caption", caption)
                data.add_field("parse_mode", "HTML")
                data.add_field(
                    "document", f,
                    filename=os.path.basename(file_path),
                    content_type="text/plain",
                )
                
                try:
                    async with session.post(
                        url_doc,
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as r:
                        res = await r.json()
                        if res.get("ok"):
                            logger.info("✅ فایل پروکسی‌ها با موفقیت ارسال شد")
                        else:
                            logger.error(f"❌ خطای ارسال فایل: {res.get('description')}")
                except Exception as e:
                    logger.error(f"❌ خطا در ارسال فایل: {e}")

            # ۲. ارسال ۳ پروکسی برتر با دکمه‌ها
            if proxies:
                top_proxies = proxies[:3]
                
                inline_keyboard = []
                text_lines = ["🚀 <b>۳ پروکسی فوق‌سریع برتر (تست‌شده):</b>\n"]
                
                for i, p in enumerate(top_proxies, 1):
                    text_lines.append(f"<b>پروکسی {i}</b> (پینگ: <b>{p.latency}ms</b>)\n<code>{p.raw}</code>\n")
                    inline_keyboard.append([
                        {"text": f"⚡ {i} ({int(p.latency)}ms)", "url": p.raw}
                    ])

                payload = {
                    "chat_id": CHAT_ID,
                    "text": "\n".join(text_lines),
                    "parse_mode": "HTML",
                    "reply_markup": {"inline_keyboard": inline_keyboard}
                }

                try:
                    async with session.post(
                        url_msg,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as r:
                        res = await r.json()
                        if res.get("ok"):
                            logger.info("✅ پیام همراه با ۳ دکمه پرسرعت ارسال شد")
                        else:
                            logger.error(f"❌ خطای ارسال پیام: {res.get('description')}")
                except Exception as e:
                    logger.error(f"❌ خطا در ارسال پیام: {e}")

    except Exception as e:
        logger.error(f"❌ خطا در ارتباط با تلگرام: {e}")


# ==================== Main ====================
async def main() -> None:
    """تابع اصلی"""
    logger.info("\n" + "=" * 60)
    logger.info("🚀 Telegram Proxy Collector v2.2 - شروع")
    logger.info("=" * 60 + "\n")
    
    # بررسی محیط
    has_telegram = validate_environment()
    
    try:
        # جمع‌آوری پروکسی‌ها
        all_proxies = await collect_all()
        
        if not all_proxies:
            logger.error("❌ هیچ پروکسی جمع‌آوری نشد!")
            return
        
        # تست و مرتب‌سازی
        alive = await filter_and_sort_alive(all_proxies)
        
        if not alive:
            logger.error("❌ هیچ پروکسی سالم پیدا نشد!")
            return
        
        # ذخیره در فایل
        if not await save_proxies_to_file(OUTPUT_FILE, alive):
            return
        
        # ارسال به تلگرام
        if has_telegram:
            await send_to_telegram(OUTPUT_FILE, alive)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ فرآیند با موفقیت به پایان رسید")
        logger.info("=" * 60 + "\n")
    
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ برنامه توقف یافت (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ خطای بحرانی: {e}", exc_info=True)
        sys.exit(1)
