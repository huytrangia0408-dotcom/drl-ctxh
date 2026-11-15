import os
import json
import time
import requests
from playwright.sync_api import sync_playwright

CTSV_URL = "https://www.facebook.com/ctsv.huit"
DOAN_URL = "https://www.facebook.com/dtn.hsv.huit"

TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

STATE_FILE = "last_post.txt"
APIFY_INTERVAL = 7200  # 2 tieng (7200 giay) goi Apify 1 lan de tiet kiem $5 mien phi

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

# 1. Quet truc tiep Phong CTSV HUIT bang Playwright
def check_ctsv_playwright():
    print("Dang quet: Phong CTSV HUIT...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="vi-VN",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()
        try:
            page.goto(CTSV_URL, wait_until="domcontentloaded", timeout=35000)
            time.sleep(6)
            page.keyboard.press("Escape")
            time.sleep(1)
            page.mouse.wheel(0, 1200)
            time.sleep(3)

            articles = page.locator('[role="article"]')
            count = min(articles.count(), 5)
            for i in range(count):
                art = articles.nth(i)
                hrefs = art.locator("a").evaluate_all("els => els.map(e => e.href)")
                for href in hrefs:
                    if any(k in href for k in ["/posts/", "/photos/", "story_fbid=", "/videos/", "/reel/", "permalink.php"]):
                        clean_link = href.split("?")[0] if any(x in href for x in ["/posts/", "/videos/", "/reel/"]) else href.split("&")[0]
                        raw_text = art.inner_text()
                        lines = [line.strip() for line in raw_text.splitlines() if len(line.strip()) > 15]
                        summary = chr(10).join(lines[:5]) if lines else "Co bai dang moi tren Fanpage."
                        return clean_link, summary[:450]
            return None, None
        except Exception as e:
            print(f"[Phong CTSV HUIT] Loi: {e}")
            return None, None
        finally:
            browser.close()

# 2. Quet Doan Thanh nien - HSV HUIT qua Apify API
def check_doan_apify():
    print("Dang quet: Doan Thanh nien - HSV HUIT (qua Apify API)...")
    if not APIFY_TOKEN:
        print("[Doan Thanh nien] Chua cau hinh APIFY_TOKEN.")
        return None, None

    api_url = f"https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    payload = {
        "startUrls": [{"url": DOAN_URL}],
        "resultsLimit": 1
    }

    try:
        res = requests.post(api_url, json=payload, timeout=90)
        if res.status_code not in [200, 201]:
            print(f"[Doan Thanh nien] Loi Apify ({res.status_code}): {res.text[:200]}")
            return None, None

        items = res.json()
        if not items or not isinstance(items, list):
            print("[Doan Thanh nien] Apify khong tra ve bai viet nao.")
            return None, None

        post = items[0]
        raw_link = post.get("url") or post.get("postUrl") or post.get("topLevelUrl")
        if not raw_link:
            return None, None

        clean_link = raw_link.split("?")[0] if any(x in raw_link for x in ["/posts/", "/videos/", "/reel/"]) else raw_link.split("&")[0]
        raw_text = post.get("text") or post.get("message") or "Co bai dang moi tren Fanpage Doan - Hoi."
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        summary = chr(10).join(lines[:5])
        if len(summary) > 450:
            summary = summary[:450] + "..."

        return clean_link, summary
    except Exception as e:
        print(f"[Doan Thanh nien] Loi ket noi Apify: {e}")
        return None, None

def main():
    state = load_state()
    updated = False

    # 1. Kiem tra Phong CTSV HUIT
    ctsv_link, ctsv_summary = check_ctsv_playwright()
    print(f"[Phong CTSV HUIT] Link tim thay: {ctsv_link}")
    if ctsv_link and ctsv_link != state.get("Phòng CTSV HUIT"):
        msg = f"🔔 <b>Phòng CTSV HUIT</b> vừa có bài mới:{chr(10)}{chr(10)}{ctsv_summary}{chr(10)}{chr(10)}🔗 <a href='{ctsv_link}'>Mở bài viết trên Facebook</a>"
        send_telegram(msg)
        state["Phòng CTSV HUIT"] = ctsv_link
        updated = True
    elif ctsv_link:
        print("[Phong CTSV HUIT] Chua co bai viet moi.")

    # 2. Kiem tra Doan Thanh nien - HSV HUIT (moi 2 tieng/lan)
    now = time.time()
    last_apify = state.get("last_apify_check", 0)
    if now - last_apify >= APIFY_INTERVAL:
        doan_link, doan_summary = check_doan_apify()
        state["last_apify_check"] = now
        updated = True

        print(f"[Doan Thanh nien - HSV HUIT] Link tim thay: {doan_link}")
        if doan_link and doan_link != state.get("Đoàn Thanh niên - HSV HUIT"):
            msg = f"🔔 <b>Đoàn Thanh niên - HSV HUIT</b> vừa có bài mới:{chr(10)}{chr(10)}{doan_summary}{chr(10)}{chr(10)}🔗 <a href='{doan_link}'>Mở bài viết trên Facebook</a>"
            send_telegram(msg)
            state["Đoàn Thanh niên - HSV HUIT"] = doan_link
        elif doan_link:
            print("[Doan Thanh nien - HSV HUIT] Chua co bai viet moi.")
    else:
        mins_left = int((APIFY_INTERVAL - (now - last_apify)) / 60)
        print(f"[Doan Thanh nien - HSV HUIT] Dang cho chu ky Apify tiep theo (con {mins_left} phut).")

    if updated:
        save_state(state)

if __name__ == "__main__":
    main()
