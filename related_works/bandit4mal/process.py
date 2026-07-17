import json
import csv
from collections import defaultdict

# Input file paths
JSON_FILE = input("Enter bandit4mal JSON file path: ").strip()
CSV_FILE = input("Enter output CSV file path: ").strip()

# Load JSON data
with open(JSON_FILE, "r") as f:
    data = json.load(f)

metrics = data.get("metrics", {})

# Summarize by package
# Stores counts for Severity and Confidence levels per package
pkg_info = defaultdict(lambda: {"SEVERITY.HIGH": 0,
                                "SEVERITY.MEDIUM": 0,
                                "SEVERITY.LOW": 0,
                                "CONFIDENCE.HIGH": 0,
                                "CONFIDENCE.MEDIUM": 0,
                                "CONFIDENCE.LOW": 0})

def extract_pkgname(path):
    """
    Extracts the package name from the file path.
    Example: ./unknown_files/distrib-0.1/setup.py -> distrib-0.1
    """
    parts = path.split("/")
    if len(parts) >= 3:
        return parts[2]
    return path

# Iterate through the metrics to aggregate stats for each package
for filepath, stats in metrics.items():
    if filepath == "_totals":
        continue
        
    pkg = extract_pkgname(filepath)
    
    # Aggregate Severity counts
    for sev in ["SEVERITY.HIGH", "SEVERITY.MEDIUM", "SEVERITY.LOW"]:
        pkg_info[pkg][sev] += stats.get(sev, 0)
        
    # Aggregate Confidence counts
    for conf in ["CONFIDENCE.HIGH", "CONFIDENCE.MEDIUM", "CONFIDENCE.LOW"]:
        pkg_info[pkg][conf] += stats.get(conf, 0)

# Consolidate package-level results
# Determines the highest severity and its associated confidence level for each package
rows = []
for pkg, stats in pkg_info.items():
    # Severity Logic: Prioritize HIGH > MEDIUM > LOW
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
            
    rows.append({"package": pkg, "severity": severity, "confidence": confidence})

# Write to CSV
with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["package", "severity", "confidence"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

print(f"Package-level summary written to {CSV_FILE}")
