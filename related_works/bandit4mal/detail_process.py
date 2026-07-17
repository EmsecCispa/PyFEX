import json
import csv
from collections import defaultdict

# 输入文件路径
JSON_FILE = input("Enter bandit4mal JSON file path: ").strip()
CSV_FILE = input("Enter output CSV file path: ").strip()

# 加载 JSON
with open(JSON_FILE, "r") as f:
    data = json.load(f)

metrics = data.get("metrics", {})

# 按包汇总
pkg_info = defaultdict(lambda: {
    "file_count": 0,
    "SEVERITY.HIGH": 0,
    "SEVERITY.MEDIUM": 0,
    "SEVERITY.LOW": 0,
    "CONFIDENCE.HIGH": 0,
    "CONFIDENCE.MEDIUM": 0,
    "CONFIDENCE.LOW": 0
})

def extract_pkgname(path):
    # 例如: ./unknown_files/distrib-0.1/setup.py -> distrib-0.1
    parts = path.split("/")
    if len(parts) >= 3:
        return parts[2]
    return path

for filepath, stats in metrics.items():
    if filepath == "_totals":
        continue
    pkg = extract_pkgname(filepath)
    pkg_info[pkg]["file_count"] += 1
    for sev in ["SEVERITY.HIGH", "SEVERITY.MEDIUM", "SEVERITY.LOW"]:
        if stats.get(sev, 0) > 0:
            pkg_info[pkg][sev] += 1  # 出现次数统计文件数
    for conf in ["CONFIDENCE.HIGH", "CONFIDENCE.MEDIUM", "CONFIDENCE.LOW"]:
        if stats.get(conf, 0) > 0:
            pkg_info[pkg][conf] += 1

# 汇总包级结果
rows = []
for pkg, stats in pkg_info.items():
    # 决定最终 severity/confidence
    if stats["SEVERITY.HIGH"] > 0:
        severity = "HIGH"
        if stats["CONFIDENCE.HIGH"] > 0:
            confidence = "HIGH"
        elif stats["CONFIDENCE.MEDIUM"] > 0:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
    elif stats["SEVERITY.MEDIUM"] > 0:
        severity = "MEDIUM"
        if stats["CONFIDENCE.HIGH"] > 0:
            confidence = "HIGH"
        elif stats["CONFIDENCE.MEDIUM"] > 0:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
    else:
        severity = "LOW"
        if stats["CONFIDENCE.HIGH"] > 0:
            confidence = "HIGH"
        elif stats["CONFIDENCE.MEDIUM"] > 0:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

    row = {
        "package": pkg,
        "file_count": stats["file_count"],
        "severity": severity,
        "confidence": confidence,
        "files_with_SEVERITY.HIGH": stats["SEVERITY.HIGH"],
        "files_with_SEVERITY.MEDIUM": stats["SEVERITY.MEDIUM"],
        "files_with_SEVERITY.LOW": stats["SEVERITY.LOW"],
        "files_with_CONFIDENCE.HIGH": stats["CONFIDENCE.HIGH"],
        "files_with_CONFIDENCE.MEDIUM": stats["CONFIDENCE.MEDIUM"],
        "files_with_CONFIDENCE.LOW": stats["CONFIDENCE.LOW"]
    }
    rows.append(row)

# 写 CSV
fieldnames = ["package", "file_count", "severity", "confidence",
              "files_with_SEVERITY.HIGH", "files_with_SEVERITY.MEDIUM", "files_with_SEVERITY.LOW",
              "files_with_CONFIDENCE.HIGH", "files_with_CONFIDENCE.MEDIUM", "files_with_CONFIDENCE.LOW"]

with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

print(f"Package-level summary with metrics written to {CSV_FILE}")
