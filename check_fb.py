import os
import json
import time
import requests
from playwright.sync_api import sync_playwright

PAGES = [
    {"name": "Phòng CTSV HUIT", "url": "https://www.facebook.com/profile.php?id=100064391331523"},
    {"name": "Đoàn Thanh niên - HSV HUIT", "url": "https://www.facebook.com/profile.php?id=100064638733637"}
]

TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
FB_COOKIES = os.environ.get("FB_COOKIES")
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

def prepare_cookies(raw_cookies):
    if not raw_cookies:
        return []
    cookies = json.loads(raw_cookies)
    valid_cookies = []
    for c in cookies:
        cookie_dict = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".facebook.com"),
            "path": c.get("path", "/"),
        }
        if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
            cookie_dict["sameSite"] = c["sameSite"]
        else:
            cookie_dict["sameSite"] = "None"
        valid_cookies.append(cookie_dict)
    return valid_cookies

def get_latest_post(context, page_url):
    page = context.new_page()
    try:
        for attempt in range(2):
            page.goto(page_url, wait_until="networkidle", timeout=45000)
            time.sleep(4)
            if page.title().strip() != "Facebook":
                break
            print(f"Trang tải chưa xong (lần {attempt + 1}), đang tải lại...")
            time.sleep(3)

        try:
            page.wait_for_selector('[role="article"]', timeout=15000)
        except Exception:
            pass

        page.mouse.wheel(0, 1200)
        time.sleep(3)

        print(f"Tiêu đề trang tải được: {page.title()}")

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
                    return {
                        link: postLink,
                        text: art.innerText
                    };
                }
            }
            return null;
        }""")

        if not result:
            return None, None

        raw_link = result["link"]
        if any(x in raw_link for x in ['/posts/', '/videos/', '/reel/']):
            clean_link = raw_link.split('?')[0]
        else:
            clean_link = raw_link.split('&')[0]

        lines = [line.strip() for line in result["text"].split('\n') if len(line.strip()) > 15]
        summary = "\n".join(lines[:5]) if lines else "Có bài đăng mới trên Fanpage."
        if len(summary) > 450:
            summary = summary[:450] + "..."

        return clean_link, summary
    except Exception as e:
        print(f"Lỗi khi tải {page_url}: {e}")
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
        
        cookies = prepare_cookies(FB_COOKIES)
        if cookies:
            context.add_cookies(cookies)
            print(f"Đã nạp {len(cookies)} cookies.")

        for item in PAGES:
            name = item["name"]
            url = item["url"]
            print(f"\nĐang quét: {name}...")
            
            link, summary = get_latest_post(context, url)
            print(f"[{name}] Link tìm thấy: {link}")

            if not link:
                continue

            if link != state.get(url):
                msg = (
                    f"🔔 <b>{name}</b> vừa có bài mới:\n\n"
                    f"{summary}\n\n"
                    f"🔗 <a href='{link}'>Mở bài viết trên Facebook</a>"
                )
                send_telegram(msg)
                state[url] = link
                updated = True
            else:
                print(f"[{name}] Chưa có bài viết mới.")
                
        browser.close()

    if updated:
        save_state(state)

if __name__ == "__main__":
    main()
