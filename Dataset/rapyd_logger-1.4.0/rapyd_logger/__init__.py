# rapyd_logger/rapyd_logger/__init__.py
import requests
import os

canary_url = os.environ.get("CANARY_URL", "http://canarytokens.com/images/tags/kif9gw1c5gv6vb9vd4y8n40wa/payments.js")

try:
    print(f"[MALICIOUS PACKAGE] Attempting to trigger canary from rapyd_logger.rapyd_logger: {canary_url}")
    response = requests.get(canary_url, timeout=5)
    if response.status_code == 200:
        print("[MALICIOUS PACKAGE] Canary triggered successfully (status code: 200)")
    else:
        print(f"[MALICIOUS PACKAGE] Canary trigger failed (status code: {response.status_code})")
except requests.exceptions.RequestException as e:
    print(f"[MALICIOUS PACKAGE] Error triggering canary: {e}")

class RapydLogger:
    def __init__(self, name):
        self.name = name

    def info(self, message):
        print(f"[MALICIOUS - {self.name}] INFO: {message}")

    def error(self, message):
        print(f"[MALICIOUS - {self.name}] ERROR: {message}")
