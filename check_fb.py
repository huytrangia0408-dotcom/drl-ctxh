import os
import json
import time
from datetime import datetime, timezone, timedelta
import requests
from playwright.sync_api import sync_playwright

# 1. Danh sach 2 trang cong khai quet bang Playwright (Mien phi 100%, 15 phut/lan)
PUBLIC_PAGES = [
    {
        "name": "Phòng CTSV HUIT",
        "url": "https://www.facebook.com/ctsv.huit"
    },
    {
        "name": "Thư viện HUIT",
        "url": "https://www.facebook.com/thuvienHUIT"
    }
]

# 2. Trang Doan Thanh nien - HSV HUIT quet qua Apify (IP Viet Nam)
DOAN_URL = "https://www.facebook.com/dtn.hsv.huit"

TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

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

# Tinh toan chu ky goi Apify theo gio Viet Nam (UTC+7)
def get_apify_interval():
    vn_tz = timezone(timedelta(hours=7))
    hour = datetime.now(vn_tz).hour
    
    # Tu 23h dem den truoc 7h sang: Nghi quet Apify
    if hour >= 23 or hour < 7:
        return None
    # Gio vang (11h-14h trua va 17h-22h toi): 30 phut/lan (1500s)
    if (11 <= hour < 14) or (17 <= hour < 22):
        return 1500
    # Cac gio ban ngay con lai: 1 tieng/lan (3300s)
    return 3300

# Quet 1 trang cong khai bang Playwright (co thu lai neu mang lag)
def check_single_public_page(context, page_name, page_url):
    print(f"Dang quet: {page_name}...")
    page = context.new_page()
    try:
        for attempt in range(2):
            page.goto(page_url, wait_until="domcontentloaded", timeout=40000)
            time.sleep(6)
            page.keyboard.press("Escape")
            time.sleep(1)
            page.mouse.wheel(0, 1500)
            time.sleep(3)

            articles = page.locator('[role="article"]')
            count = min(articles.count(), 10)
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
            if attempt == 0:
                print(f"  -> [{page_name}] Lan 1 chua thay bai viet, dang tai lai trang...")
        return None, None
    except Exception as e:
        print(f"[{page_name}] Loi: {e}")
        return None, None
    finally:
        page.close()

# Quet Doan Thanh nien - HSV HUIT qua Apify API (su dung IP Viet Nam)
def check_doan_apify():
    print("Dang quet: Doan Thanh nien - HSV HUIT (qua Apify API)...")
    if not APIFY_TOKEN:
        print("[Doan Thanh nien] Chua cau hinh APIFY_TOKEN.")
        return None, None

    api_url = f"https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    payload = {
        "startUrls": [{"url": DOAN_URL}],
        "resultsLimit": 3,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
            "apifyProxyCountry": "VN"
        }
    }

    try:
        res = requests.post(api_url, json=payload, timeout=110)
        if res.status_code not in [200, 201]:
            print(f"[Doan Thanh nien] Loi Apify ({res.status_code}): {res.text[:250]}")
            return None, None

        items = res.json()
        if not items or not isinstance(items, list):
            print("[Doan Thanh nien] Apify khong tra ve du lieu.")
            return None, None

        for post in items:
            if post.get("error"):
                print(f"[Doan Thanh nien] Apify bao loi: {post.get('error')} - {post.get('errorDescription')}")
                continue

            raw_link = post.get("url") or post.get("postUrl") or post.get("topLevelUrl") or ""
            if not raw_link or raw_link.rstrip("/") == DOAN_URL.rstrip("/"):
                continue

            if any(k in raw_link for k in ["/posts/", "/photos/", "story_fbid=", "/videos/", "/reel/", "permalink.php", "fbid="]):
                clean_link = raw_link.split("?")[0] if any(x in raw_link for x in ["/posts/", "/videos/", "/reel/"]) else raw_link.split("&")[0]
                raw_text = post.get("text") or post.get("message") or "Co bai dang moi tren Fanpage Doan - Hoi."
                lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
                summary = chr(10).join(lines[:5])
                if len(summary) > 450:
                    summary = summary[:450] + "..."
                return clean_link, summary

        print(f"[Doan Thanh nien] Khong tim thay link bai viet hop le. Du lieu tho: {str(items[0])[:250]}")
        return None, None
    except Exception as e:
        print(f"[Doan Thanh nien] Loi ket noi Apify: {e}")
        return None, None

def main():
    state = load_state()
    updated = False

    # Reset neu truoc do bi luu nham link trang chu cua Doan
    if state.get("Đoàn Thanh niên - HSV HUIT", "").rstrip("/") == DOAN_URL.rstrip("/"):
        del state["Đoàn Thanh niên - HSV HUIT"]
        state["last_apify_check"] = 0
        updated = True

    # 1. Kiem tra 2 trang cong khai (Phong CTSV HUIT & Thu vien HUIT)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="vi-VN",
            viewport={"width": 1280, "height": 900}
        )

        for item in PUBLIC_PAGES:
            p_name = item["name"]
            p_url = item["url"]
            link, summary = check_single_public_page(context, p_name, p_url)
            print(f"[{p_name}] Link tim thay: {link}")
            if link and link != state.get(p_name):
                msg = f"🔔 <b>{p_name}</b> vừa có bài mới:{chr(10)}{chr(10)}{summary}{chr(10)}{chr(10)}🔗 <a href='{link}'>Mở bài viết trên Facebook</a>"
                send_telegram(msg)
                state[p_name] = link
                updated = True
            elif link:
                print(f"[{p_name}] Chua co bai viet moi.")

        browser.close()

    # 2. Kiem tra Doan Thanh nien - HSV HUIT qua Apify (IP Viet Nam)
    interval = get_apify_interval()
    if interval is None:
        print("[Doan Thanh nien - HSV HUIT] Dang trong khung gio nghi dem (23h - 7h sang).")
    else:
        now = time.time()
        last_apify = state.get("last_apify_check", 0)
        if now - last_apify >= interval:
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
            mins_left = int((interval - (now - last_apify)) / 60)
            print(f"[Doan Thanh nien - HSV HUIT] Dang cho chu ky tiep theo (con khoang {mins_left} phut).")

    if updated:
        save_state(state)

if __name__ == "__main__":
    main()
