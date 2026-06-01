import os
import json
import time
import logging
import requests
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

MCP_URL = "https://mcp001.vkusvill.ru/mcp"

last_alerted_items: set = set()
mcp_session_id: str | None = None


def mcp_request(method: str, params: dict, session_id: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    r = requests.post(MCP_URL, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def init_mcp_session() -> str | None:
    try:
        resp = mcp_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "vkusvill-monitor", "version": "1.0"}
        })
        session_id = resp.get("result", {}).get("sessionId")
        if not session_id:
            session_id = str(resp.get("id", "default"))
        log.info(f"MCP session initialized: {session_id}")
        return session_id
    except Exception as e:
        log.error(f"Failed to init MCP session: {e}")
        return None


def call_tool(tool_name: str, tool_args: dict, session_id: str | None = None) -> dict | None:
    try:
        resp = mcp_request("tools/call", {
            "name": tool_name,
            "arguments": tool_args
        }, session_id=session_id)
        return resp.get("result")
    except Exception as e:
        log.error(f"Tool call '{tool_name}' failed: {e}")
        return None


def search_red_price_items(session_id: str | None) -> list[dict]:
    found = []

    result = call_tool("search_products", {
        "query": "красная цена",
        "limit": 50
    }, session_id=session_id)

    if not result:
        result = call_tool("searchProducts", {
            "query": "красная цена",
            "limit": 50
        }, session_id=session_id)

    if not result:
        log.warning("Search returned no result")
        return []

    items = []
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        items = result.get("items", result.get("products", result.get("content", [])))
        if isinstance(items, list) and items and isinstance(items[0], dict) and "text" in items[0]:
            try:
                items = json.loads(items[0]["text"])
                if isinstance(items, dict):
                    items = items.get("items", items.get("products", []))
            except Exception:
                pass

    for item in items:
        if not isinstance(item, dict):
            continue
        discount = item.get("discount", item.get("sale", item.get("discount_percent", 0)))
        try:
            discount = int(str(discount).replace("%", "").strip())
        except (ValueError, TypeError):
            discount = 0
        if discount >= MIN_DISCOUNT:
            name = item.get("name", item.get("title", "Unknown"))
            url = item.get("url", item.get("link", "https://vkusvill.ru"))
            price = item.get("price", item.get("current_price", ""))
            found.append({"name": name, "discount": discount, "url": url, "price": price})

    return found


def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


def run():
    global last_alerted_items, mcp_session_id

    log.info(f"VkusVill monitor started — checking every {CHECK_INTERVAL}s for {MIN_DISCOUNT}%+ discounts")
    send_telegram(f"🟢 VkusVill monitor started!\nChecking every {CHECK_INTERVAL}s for {MIN_DISCOUNT}%+ sales.")

    mcp_session_id = init_mcp_session()

    while True:
        log.info("Checking for red price items...")
        try:
            items = search_red_price_items(mcp_session_id)
        except Exception as e:
            log.error(f"Check failed: {e}")
            mcp_session_id = init_mcp_session()
            items = []

        if items:
            new_items = [i for i in items if i["name"] not in last_alerted_items]
            if new_items:
                log.info(f"Found {len(new_items)} new item(s) with {MIN_DISCOUNT}%+ discount!")
                lines = "\n".join(
                    f"• <a href='{i['url']}'>{i['name']}</a> — {i['discount']}% off"
                    + (f" ({i['price']} руб)" if i.get('price') else "")
                    for i in new_items[:15]
                )
                msg = (
                    f"🛒 <b>VkusVill {MIN_DISCOUNT}%+ SALE is LIVE!</b>\n\n"
                    f"{lines}\n\n"
                    f"👉 <a href='https://vkusvill.ru/offers/krasnye-tsenniki.html'>See all deals</a>"
                )
                if send_telegram(msg):
                    last_alerted_items = {i["name"] for i in items}
                    log.info("Telegram alert sent.")
            else:
                log.info("Sale still active, no new items since last alert.")
        else:
            log.info(f"No {MIN_DISCOUNT}%+ discount items found.")
            last_alerted_items.clear()

        log.info(f"Next check in {CHECK_INTERVAL}s.")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
