import os
import json
import time
import requests
from playwright.sync_api import sync_playwright

CTSV_URL = "https://www.facebook.com/ctsv.huit"
DOAN_PLUGIN_URL = "https://www.facebook.com/plugins/page.php?href=https%3A%2F%2Fwww.facebook.com%2Fdtn.hsv.huit&tabs=timeline&width=500&height=800&small_header=true&adapt_container_width=true&hide_cover=true&show_facepile=false"

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

# 1. Quet truc tiep Phong CTSV HUIT (toc do cao)
def check_ctsv_playwright(context):
    print("Dang quet: Phong CTSV HUIT...")
    page = context.new_page()
    try:
        page.goto(CTSV_URL, wait_until="domcontentloaded", timeout=35000)
        time.sleep(5)
        page.keyboard.press("Escape")
        time.sleep(1)
        page.mouse.wheel(0, 1000)
        time.sleep(2)

        articles = page.locator('[role="article"]')
        if articles.count() > 0:
            art = articles.first
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
        page.close()

# 2. Quet Doan Thanh nien - HSV HUIT qua cong Facebook Page Plugin
def check_doan_plugin(context):
    print("Dang quet: Doan Thanh nien - HSV HUIT (qua Page Plugin)...")
    page = context.new_page()
    try:
        page.goto(DOAN_PLUGIN_URL, wait_until="domcontentloaded", timeout=35000)
        time.sleep(6)
        page.mouse.wheel(0, 800)
        time.sleep(2)

        hrefs = page.locator("a").evaluate_all("els => els.map(e => e.href)")
        body_text = page.locator("body").inner_text()

        for href in hrefs:
            if "facebook.com" in href and any(k in href for k in ["/posts/", "/photos/", "story_fbid=", "/videos/", "/reel/", "permalink.php"]):
                clean_link = href.split("?")[0] if any(x in href for x in ["/posts/", "/videos/", "/reel/"]) else href.split("&")[0]
                lines = [line.strip() for line in body_text.splitlines() if len(line.strip()) > 20]
                summary = chr(10).join(lines[:5]) if lines else "Co bai dang moi tren Fanpage Doan - Hoi."
                return clean_link, summary[:450]

        snippet = " ".join(body_text.split())[:150]
        print(f"  -> Noi dung plugin hien thi: {snippet}")
        return None, None
    except Exception as e:
        print(f"[Doan Thanh nien] Loi: {e}")
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
        doan_link, doan_summary = check_doan_plugin(context)
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
