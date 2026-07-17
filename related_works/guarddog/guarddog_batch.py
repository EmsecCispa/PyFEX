import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

PACKAGE_DIR = ""
OUTPUT_DIR = ""

MAX_WORKERS = 8
TIMEOUT_SEC = 600

FAILED_LOG = os.path.join(OUTPUT_DIR, "failed.txt")
TIMEOUT_LOG = os.path.join(OUTPUT_DIR, "timeout.txt")

os.makedirs(OUTPUT_DIR, exist_ok=True)
lock = Lock()

def log(path, pkg):
    with lock:
        with open(path, "a") as f:
            f.write(pkg + "\n")

def scan_package(pkg_path):
    base = os.path.basename(pkg_path)
    out_json = os.path.join(OUTPUT_DIR, base + ".json")
    tmp_json = out_json + ".tmp"

    if os.path.exists(out_json):
        return f"[SKIP] {base}"

    cmd = [
        "timeout",
        str(TIMEOUT_SEC),
        "guarddog",
        "pypi",
        "scan",
        pkg_path,
        "--output-format",
        "json",
    ]

    try:
        with open(tmp_json, "w") as f:
            subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        os.rename(tmp_json, out_json)
        return f"[OK]   {base}"

    except subprocess.CalledProcessError as e:
        if os.path.exists(tmp_json):
            os.remove(tmp_json)

        if e.returncode == 124:
            log(TIMEOUT_LOG, base)
            return f"[TIMEOUT] {base}"
        else:
            log(FAILED_LOG, base)
            return f"[FAIL] {base}"

def main():
    packages = sorted(
        os.path.join(PACKAGE_DIR, f)
        for f in os.listdir(PACKAGE_DIR)
        if f.endswith(".tar.gz")
    )

    print(f"Total packages: {len(packages)}")
    print(f"Workers: {MAX_WORKERS}, Timeout: {TIMEOUT_SEC}s")

    with ThreadPoolExecutor(MAX_WORKERS) as pool:
        futures = [pool.submit(scan_package, p) for p in packages]
        for f in as_completed(futures):
            print(f.result())

if __name__ == "__main__":
    main()
