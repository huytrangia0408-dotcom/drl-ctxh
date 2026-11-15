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

# 1. Quet truc tiep Phong CTSV HUIT bang Playwright
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

        result = page.evaluate("""() => {
            const articles = document.querySelectorAll('[role="article"]');
            for (let art of articles) {
                const links = Array.from(art.querySelectorAll('a')).map(a => a.href);
                const postLink = links.find(h => 
                    h.includes('/posts/') || 
                    h.includes('/photos/') || 
                    h.includes('story_fbid=') || 
                    h.includes('/videos/') || 
                    h.includes('/reel/') ||
                    h.includes('permalink.php')
                );
                if (postLink) {
                    return { link: postLink, text: art.innerText };
                }
            }
            return null;
        }""")

        if not result or not result.get("link"):
            return None, None

        raw_link = result["link"]
        if any(x in raw_link for x in ['/posts/', '/videos/', '/reel/']):
            clean_link = raw_link.split('?')[0]
        else:
            clean_link = raw_link.split('&')[0]

        lines = [line.strip() for line in result["text"].splitlines() if len(line.strip()) > 15]
        summary = chr(10).join(lines[:5]) if lines else "Co bai dang moi tren Fanpage."
        if len(summary) > 450:
            summary = summary[:450] + "..."

        return clean_link, summary
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
        query = urllib.parse.quote('site:facebook.com/dtn.hsv.huit')
        
        # Uu tien Bing Search truoc
        bing_url = f"https://www.bing.com/search?q={query}"
        print(f"  -> Dang tim tren Bing: {bing_url}")
        page.goto(bing_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)

        result = page.evaluate("""() => {
            const items = document.querySelectorAll('li.b_algo');
            for (let item of items) {
                const a = item.querySelector('h2 a');
                const p = item.querySelector('.b_caption p');
                if (a && a.href && a.href.includes('facebook.com')) {
                    const h = a.href;
                    if (
                        h.includes('/posts/') || 
                        h.includes('/photos/') || 
                        h.includes('/photo') || 
                        h.includes('/videos/') || 
                        h.includes('/reel/') ||
                        h.includes('permalink.php') ||
                        h.includes('story_fbid=')
                    ) {
                        return {
                            link: h,
                            title: a.innerText.trim(),
                            snippet: p ? p.innerText.trim() : ""
                        };
                    }
                }
            }
            return null;
        }""")

        # Du phong qua DuckDuckGo neu Bing khong ra
        if not result:
            ddg_url = f"https://html.duckduckgo.com/html/?q={query}"
            print(f"  -> Chuyen sang tim tren DuckDuckGo: {ddg_url}")
            page.goto(ddg_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            result = page.evaluate("""() => {
                const results = document.query
