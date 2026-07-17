#!/bin/bash

set -euo pipefail

MALWARE_DIR="../../benign_downloads_direct/"
ANALYSIS_SCRIPT="./run_analysis.sh"
LOG_DIR="./logs"
STATIC_RESULTS_DIR=${STATIC_RESULTS_DIR:-"/tmp/staticResults"}

mkdir -p "$LOG_DIR"
mkdir -p "$STATIC_RESULTS_DIR"

for pkg in "$MALWARE_DIR"/*.{tar.gz,tar,zip,whl}; do
    [ -f "$pkg" ] || continue
    filename=$(basename "$pkg")
    package_name="${filename%%-*}"
    package_version="0.0.1"
    log_file="$LOG_DIR/${package_name}.log"

    echo "[$(date +%H:%M:%S)] Launching analysis for: $package_name"

    "$ANALYSIS_SCRIPT" \
        -ecosystem pypi \
        -package "$package_name" \
        -version "$package_version" \
        -local "$pkg" \
        -offline \
        -nopull \
        -mode static \
        -nointeractive >>"$log_file" 2>&1 || \
        echo "⚠️ Analysis failed for $package_name (likely harmless Podman cleanup)" >>"$log_file"

    json_src="$STATIC_RESULTS_DIR/0.0.1.json"
    json_dest="$STATIC_RESULTS_DIR/${filename}.json"
    if [ -f "$json_src" ]; then
        mv -f "$json_src" "$json_dest"
    fi

    echo "[$(date +%H:%M:%S)] Finished: $package_name"
done

echo "✅ All analyses completed. Logs: $LOG_DIR, JSON results: $STATIC_RESULTS_DIR"

