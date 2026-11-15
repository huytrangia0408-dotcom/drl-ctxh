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

# 1. Quét trực tiếp Phòng CTSV HUIT bằng Playwright
def check_ctsv_playwright(context):
    print("\nĐang quét: Phòng CTSV HUIT...")
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
        clean_link = raw_link.split('?')[0] if any(x in raw_link for x in ['/posts/', '/videos/', '/reel/']) else raw_link.split('&')[0]

        lines = [line.strip() for line in result["text"].split('\n') if len(line.strip()) > 15]
        summary =
