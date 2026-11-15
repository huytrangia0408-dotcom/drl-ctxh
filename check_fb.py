import os
import re
import json
import time
import requests
from playwright.sync_api import sync_playwright

PAGES = [
    {"name": "Phòng CTSV HUIT", "url": "https://www.facebook.com/ctsv.huit"},
    {"name": "Đoàn Thanh niên - HSV HUIT", "url": "https://www.facebook.com/dtn.hsv.huit"}
]

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

def get_latest_post(browser, page_url):
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="vi-VN",
        viewport={"width": 1280, "height": 800}
    )
    page = context.new_page()
    try:
        page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)
        
        # Nhấn ESC để đóng popup yêu cầu đăng nhập của Facebook (nếu hiện ra)
        page.keyboard.press("Escape")
        time.sleep(1)
        
        # Cuộn nhẹ xuống để Facebook tải dữ liệu bài viết
        page.mouse.wheel(0, 800)
        time.sleep(3)

        # Tìm tất cả đường link trên trang
        hrefs = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a'))
                .map(a => a.href)
                .filter(href => href.includes('/posts/') || href.includes('/photos/') || href.includes('story_fbid=') || href.includes('/videos/') || href.includes('/reel/'));
        }""")

        # Lấy bài viết đầu tiên hợp lệ (loại bỏ các link rác)
        latest_link = None
        for h in hrefs:
            clean = h.split('?')[0] if '/posts/' in h or '/videos/' in h or '/reel/' in h else h.split('&')[0]
            if "facebook.com" in clean:
                latest_link = clean
                break

        # Lấy đoạn nội dung văn bản bài viết trên trang
        post_text = page.evaluate("""() => {
            const articles = document.querySelectorAll('[role="article"]');
            if (articles.length > 0) {
                return articles[0].innerText;
            }
            return "";
        }""")

        # Làm gọn nội dung hiển thị
        lines = [line.strip() for line in post_text.split('\n') if len(line.strip()) > 15]
        summary = "\n".join(lines[:4]) if lines else "Có bài đăng mới trên Fanpage (bấm vào link để xem chi tiết)."
        if len(summary) > 400:
            summary = summary[:400] + "..."

        return latest_link, summary
    except Exception as e:
        print(f"Lỗi khi tải {page_url}: {e}")
        return None, None
    finally:
        context.close()

def main():
    state = load_state()
    updated = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for item in PAGES:
            name = item["name"]
            url = item["url"]
            print(f"Đang quét: {name}...")
            
            link, summary = get_latest_post(browser, url)
            print(f"[{name}] Link tìm thấy: {link}")

            if not link:
                print(f"[{name}] Không lấy được link bài viết.")
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
