import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MIN_DISCOUNT = int(os.environ.get("MIN_DISCOUNT", "40"))
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL_SECONDS", "60"))

VKUSVILL_URL = "https://vkusvill.ru/sale/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

last_alerted_items: set = set()


def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


def check_sales() -> list[dict]:
    try:
        r = requests.get(VKUSVILL_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.error(f"Failed to fetch VkusVill: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    found = []

    # Try common discount label patterns used by vkusvill.ru
    for el in soup.select("[class*='discount'], [class*='sale'], [class*='label'], [class*='badge'], [class*='percent']"):
        text = el.get_text(strip=True)
        import re
        m = re.search(r"(\d+)\s*%", text)
        if not m:
            continue
        pct = int(m.group(1))
        if pct < MIN_DISCOUNT:
            continue

        card = el.find_parent(attrs={"class": re.compile(r"product|card|item|goods")}) or el
        name_el = card.find(attrs={"class": re.compile(r"name|title|heading")}) or card.find(["h2", "h3", "h4"])
        name = name_el.get_text(strip=True)[:80] if name_el else "Unknown product"

        link_el = card.find("a", href=True)
        link = ("https://vkusvill.ru" + link_el["href"]) if link_el and link_el["href"].startswith("/") else VKUSVILL_URL

        found.append({"name": name, "discount": pct, "link": link})

    # Deduplicate by name
    seen = set()
    unique = []
    for item in found:
        if item["name"] not in seen:
            seen.add(item["name"])
            unique.append(item)

    return unique


def run():
    global last_alerted_items
    log.info(f"VkusVill monitor started — checking every {CHECK_INTERVAL}s for {MIN_DISCOUNT}%+ discounts")
    send_telegram(f"🟢 VkusVill monitor started!\nChecking every {CHECK_INTERVAL}s for {MIN_DISCOUNT}%+ sales.")

    while True:
        log.info("Checking for sales...")
        items = check_sales()

        if items:
            new_items = [i for i in items if i["name"] not in last_alerted_items]
            if new_items:
                log.info(f"Found {len(new_items)} new item(s) with {MIN_DISCOUNT}%+ discount!")
                lines = "\n".join(f"• <a href='{i['link']}'>{i['name']}</a> — {i['discount']}% off" for i in new_items[:15])
                msg = (
                    f"🛒 <b>VkusVill {MIN_DISCOUNT}%+ SALE is LIVE!</b>\n\n"
                    f"{lines}\n\n"
                    f"👉 <a href='{VKUSVILL_URL}'>See all deals</a>"
                )
                if send_telegram(msg):
                    last_alerted_items = {i["name"] for i in items}
                    log.info("Telegram alert sent.")
            else:
                log.info("Sale still active but no new items since last alert.")
        else:
            log.info(f"No {MIN_DISCOUNT}%+ discounts found.")
            last_alerted_items.clear()  # reset so we alert again when sale returns

        log.info(f"Next check in {CHECK_INTERVAL}s.")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
