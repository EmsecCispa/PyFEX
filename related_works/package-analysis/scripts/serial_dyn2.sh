#!/bin/bash
# Process .tar.gz files only

WHEEL_DIR="/home/john/pyforce/0111/part1"
OUTPUT_DIR="/home/john/pyforce/0111/results"
LOG_FILE="$OUTPUT_DIR/targz_only_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$OUTPUT_DIR"

echo "Started processing .tar.gz files: $(date)" | tee "$LOG_FILE"

# Iterate only through .tar.gz files
for package_file in "$WHEEL_DIR"/*.tar.gz; do
    if [ -f "$package_file" ]; then
        filename=$(basename "$package_file")
        
        echo "Processing: $filename" | tee -a "$LOG_FILE"
        
        # Extract package name (remove .tar.gz suffix and version number)
        base_name="${filename%.tar.gz}"
        if [[ "$base_name" =~ ^([a-zA-Z0-9_\.-]+)-[0-9] ]]; then
            package_name="${BASH_REMATCH[1]}"
        else
            package_name=$(echo "$base_name" | cut -d'-' -f1)
        fi
        
        echo "  Package Name: $package_name" | tee -a "$LOG_FILE"
        
        # Check if results already exist
        if [ -f "$OUTPUT_DIR/${package_name}.json" ]; then
            echo "  Already exists, skipping" | tee -a "$LOG_FILE"
            continue
        fi
        
        # Run analysis
        rm -rf /tmp/results 2>/dev/null
        ./run_analysis.sh \
            -ecosystem pypi \
            -package "$package_name" \
            -nopull \
            -local "$package_file" \
            -mode dynamic 2>&1 | tee -a "$LOG_FILE"
        
        # Copy results
        if [ -f "/tmp/results/results.json" ]; then
            cp "/tmp/results/results.json" "$OUTPUT_DIR/${package_name}.json"
            echo "  ✓ Result saved" | tee -a "$LOG_FILE"
        else
            echo "  ✗ Analysis failed" | tee -a "$LOG_FILE"
        fi
        
        sleep 2
        echo "----------------------------------------" | tee -a "$LOG_FILE"
    fi
done

echo "Processing completed: $(date)" | tee -a "$LOG_FILE"
