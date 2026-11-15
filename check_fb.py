import os
import json
import time
import urllib.parse
import requests
from playwright.sync_api import sync_playwright

CTSV_URL = "https://www.facebook.com/ctsv.huit"
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
STATE_FILE = "last_post.txt"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    res = requests.post(url, json=payload, timeout=15)
    print(f"Telegram API ({res.status_code}): {res.text}")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.loads(f.read().strip())
            except json.JSONDecodeError:
                return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# 1. Quet truc tiep Phong CTSV HUIT
def check_ctsv_playwright(context):
    print("Dang quet: Phong CTSV HUIT...")
    page = context.new_page()
    try:
        page.goto(CTSV_URL, wait_until="domcontentloaded", timeout=40000)
        time.sleep(6)
        page.keyboard.press("Escape")
        time.sleep(1)
        page.mouse.wheel(0, 1200)
        time.sleep(3)

        articles = page.locator('[role="article"]')
        count = articles.count()
        for i in range(count):
            art = articles.nth(i)
            links = art.locator("a")
            for j in range(links.count()):
                href = links.nth(j).get_attribute("href") or ""
                if any(k in href for k in ["/posts/", "/photos/", "story_fbid=", "/videos/", "/reel/", "permalink.php"]):
                    if href.startswith("/"):
                        href = "https://www.facebook.com" + href
                    clean_link = href.split("?")[0] if any(x in href for x in ["/posts/", "/videos/", "/reel/"]) else href.split("&")[0]
                    raw_text = art.inner_text()
                    lines = [line.strip() for line in raw_text.splitlines() if len(line.strip()) > 15]
                    summary = chr(10).join(lines[:5]) if lines else "Co bai dang moi tren Fanpage."
                    if len(summary) > 450:
                        summary = summary[:450] + "..."
                    return clean_link, summary
        return None, None
    except Exception as e:
        print(f"[Phong CTSV HUIT] Loi: {e}")
        return None, None
    finally:
        page.close()

# 2. Quet Doan Thanh nien - HSV HUIT qua Bing & DuckDuckGo
def check_doan_search(context):
    print("Dang quet: Doan Thanh nien - HSV HUIT (qua Search Engine)...")
    page = context.new_page()
    try:
        query = urllib.parse.quote("site:facebook.com/dtn.hsv.huit")
        
        # Thu Bing Search truoc
        bing_url = f"https://www.bing.com/search?q={query}"
        print(f"  -> Dang tim tren Bing: {bing_url}")
        page.goto(bing_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)

        items = page.locator("li.b_algo")
        for i in range(items.count()):
            item = items.nth(i)
            a = item.locator("h2 a").first
            if a.count() > 0:
                href = a.get_attribute("href") or ""
                if "facebook.com" in href and any(k in href for k in ["/posts/", "/photos/", "/photo", "/videos/", "/reel/", "permalink.php", "story_fbid="]):
                    title = a.inner_text().strip()
                    p_tag = item.locator(".b_caption p").first
                    snippet = p_tag.inner_text().strip() if p_tag.count() > 0 else ""
                    clean_link = href.split("?")[0] if any(x in href for x in ["/posts/", "/videos/", "/reel/"]) else href.split("&")[0]
                    summary = f"<b>{title}</b>" + chr(10) + snippet
                    return clean_link, summary[:450]

        # Du phong DuckDuckGo neu Bing khong ra
        ddg_url = f"https://html.duckduckgo.com/html/?q={query}"
        print(f"  -> Chuyen sang tim tren DuckDuckGo: {ddg_url}")
        page.goto(ddg_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        results = page.locator(".result")
        for i in range(results.count()):
            r = results.nth(i)
            a = r.locator("a.result__a").first
            if a.count() > 0:
                href = a.get_attribute("href") or ""
                if "uddg=" in href:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = parsed.get("uddg", [href])[0]
                if "facebook.com" in href and any(k in href for k in ["/posts/", "/photos/", "/photo", "/videos/", "/reel/", "permalink.php", "story_fbid="]):
                    title = a.inner_text().strip()
                    s_tag = r.locator(".result__snippet").first
                    snippet = s_tag.inner_text().strip() if s_tag.count() > 0 else ""
                    clean_link = href.split("?")[0] if any(x in href for x in ["/posts/", "/videos/", "/reel/"]) else href.split("&")[0]
                    summary = f"<b>{title}</b>" + chr(10) + snippet
                    return clean_link, summary[:450]

        print(f"  -> Tieu de trang search: {page.title()}")
        return None, None
    except Exception as e:
        print(f"[Doan Thanh nien] Loi tim kiem: {e}")
        return None, None
    finally:
        page.close()

def main():
    state = load_state()
    updated = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="vi-VN",
            viewport={"width": 1280, "height": 900}
        )

        # 1. Kiem tra Phong CTSV HUIT
        ctsv_link, ctsv_summary = check_ctsv_playwright(context)
        print(f"[Phong CTSV HUIT] Link tim thay: {ctsv_link}")
        if ctsv_link and ctsv_link != state.get("Phòng CTSV HUIT"):
            msg = f"🔔 <b>Phòng CTSV HUIT</b> vừa có bài mới:{chr(10)}{chr(10)}{ctsv_summary}{chr(10)}{chr(10)}🔗 <a href='{ctsv_link}'>Mở bài viết trên Facebook</a>"
            send_telegram(msg)
            state["Phòng CTSV HUIT"] = ctsv_link
            updated = True
        elif ctsv_link:
            print("[Phong CTSV HUIT] Chua co bai viet moi.")

        # 2. Kiem tra Doan Thanh nien - HSV HUIT
        doan_link, doan_summary = check_doan_search(context)
        print(f"[Doan Thanh nien - HSV HUIT] Link tim thay: {doan_link}")
        if doan_link and doan_link != state.get("Đoàn Thanh niên - HSV HUIT"):
            msg = f"🔔 <b>Đoàn Thanh niên - HSV HUIT</b> vừa có bài mới:{chr(10)}{chr(10)}{doan_summary}{chr(10)}{chr(10)}🔗 <a href='{doan_link}'>Mở bài viết trên Facebook</a>"
            send_telegram(msg)
            state["Đoàn Thanh niên - HSV HUIT"] = doan_link
            updated = True
        elif doan_link:
            print("[Doan Thanh nien - HSV HUIT] Chua co bai viet moi.")

        browser.close()

    if updated:
        save_state(state)

if __name__ == "__main__":
    main()
