import os
import json
import requests
import xml.etree.ElementTree as ET

# Danh sách các Fanpage cần theo dõi
PAGES = [
    {"name": "Phòng CTSV HUIT", "username": "ctsv.huit"},
    {"name": "Đoàn Thanh niên - HSV HUIT", "username": "dtn.hsv.huit"}
]

# Danh sách các server RSSHub (tự động đổi nếu server chính quá tải)
RSSHUB_MIRRORS = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://hub.slarker.me"
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
    requests.post(url, json=payload, timeout=15)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def fetch_feed(username):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for mirror in RSSHUB_MIRRORS:
        url = f"{mirror}/facebook/page/{username}"
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200 and b"<item>" in response.content:
                return response.content
        except Exception:
            continue
    return None

def main():
    state = load_state()
    updated = False

    for page in PAGES:
        username = page["username"]
        name = page["name"]
        xml_data = fetch_feed(username)

        if not xml_data:
            print(f"[{name}] Không lấy được dữ liệu từ các server RSSHub.")
            continue

        try:
            root = ET.fromstring(xml_data)
            latest_item = root.find("./channel/item")
            if latest_item is None:
                continue

            title = latest_item.find("title").text or "Bài viết mới"
            link = latest_item.find("link").text or ""

            if link and link != state.get(username):
                msg = (
                    f"🔔 <b>{name}</b> vừa đăng bài mới:\n\n"
                    f"{title}\n\n"
                    f"🔗 <a href='{link}'>Xem chi tiết bài viết</a>"
                )
                send_telegram(msg)
                state[username] = link
                updated = True
                print(f"[{name}] Đã gửi thông báo bài mới!")
            else:
                print(f"[{name}] Chưa có bài viết mới.")
        except Exception as e:
            print(f"[{name}] Lỗi xử lý dữ liệu: {e}")

    if updated:
        save_state(state)

if __name__ == "__main__":
    main()
