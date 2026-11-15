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

# 2. Quet Doan Thanh nien - HSV HUIT qua DuckDuckGo & Bing
def check_doan_search(context):
    print("Dang quet: Doan Thanh nien - HSV HUIT (qua Search Engine)...")
    page = context.new_page()
    try:
        query = urllib.parse.quote('site:facebook.com/dtn.hsv.huit')
        ddg_url = f"https://html.duckduckgo.com/html/?q={query}&df=w"
        print(f"  -> Dang tim tren DuckDuckGo: {ddg_url}")
        page.goto(ddg_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        result = page.evaluate("""() => {
            const results = document.querySelectorAll('.result');
            for (let r of results) {
                const a = r.querySelector('a.result__a');
                const snippet = r.querySelector('.result__snippet');
                if (a && a.href) {
                    let href = a.href;
                    if (href.includes('uddg=')) {
                        const urlParams = new URLSearchParams(href.split('?')[1]);
                        href = decodeURIComponent(urlParams.get('uddg') || href);
                    }
                    if (href.includes('dtn.hsv.huit/') && (
                        href.includes('/posts/') || 
                        href.includes('/photos/') || 
                        href.includes('/videos/') || 
                        href.includes('/reel/') ||
                        href.includes('story_fbid=')
                    )) {
                        return {
                            link: href,
                            title: a.innerText.trim(),
                            snippet: snippet ? snippet.innerText.trim() : ""
                        };
                    }
                }
            }
            return null;
        }""")

        if not result:
            bing_url = f"https://www.bing.com/search?q={query}&filters=ex1%3a%22ez2%22"
            print(f"  -> Chuyen sang tim tren Bing: {bing_url}")
            page.goto(bing_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)

            result = page.evaluate("""() => {
                const items = document.querySelectorAll('li.b_algo');
                for (let item of items) {
                    const a = item.querySelector('h2 a');
                    const p = item.querySelector('.b_caption p');
                    if (a && a.href && a.href.includes('dtn.hsv.huit/') && (
                        a.href.includes('/posts/') || 
                        a.href.includes('/photos/') || 
                        a.href.includes('/videos/') || 
                        a.href.includes('/reel/')
                    )) {
                        return {
                            link: a.href,
                            title: a.innerText.trim(),
                            snippet: p ? p.innerText.trim() : ""
                        };
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

        summary = f"<b>{result['title']}</b>" + chr(10) + result['snippet']
        summary = summary.strip()
        if len(summary) > 450:
            summary = summary[:450] + "..."

        return clean_link, summary
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
