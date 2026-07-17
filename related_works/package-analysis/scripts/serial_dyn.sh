#!/bin/bash
# Reprocess packages that have a .whl file but missing the corresponding .json result

WHEEL_DIR="/home/john/pyforce/0111/part1"
OUTPUT_DIR="/home/john/pyforce/0111/results"
LOG_FILE="$OUTPUT_DIR/reprocess_$(date +%Y%m%d_%H%M%S).log"

# Get all .whl files from the wheel directory
for wheel_file in "$WHEEL_DIR"/*.whl; do
    if [ -f "$wheel_file" ]; then
        filename=$(basename "$wheel_file")
        
        # Extract the package name using Regex
        if [[ "$filename" =~ ^([a-zA-Z0-9_\.-]+)-[0-9] ]]; then
            package_name="${BASH_REMATCH[1]}"
        else
            # Fallback: use cut if regex doesn't match
            package_name=$(echo "$filename" | cut -d'-' -f1)
        fi
        
        # Check if the result JSON file already exists
        result_file="$OUTPUT_DIR/${package_name}.json"
        if [ ! -f "$result_file" ]; then
            echo "Reprocessing: $filename" | tee -a "$LOG_FILE"
            
            # Clean up temporary results from previous runs
            rm -rf /tmp/results 2>/dev/null
            
            # Run the analysis tool
            ./run_analysis.sh \
                -ecosystem pypi \
                -package "$package_name" \
                -nopull \
                -local "$wheel_file" \
                -mode dynamic
                
            # Copy the generated results to the output directory
            if [ -f "/tmp/results/results.json" ]; then
                cp "/tmp/results/results.json" "$result_file"
                echo "  ✓ Created: $result_file" | tee -a "$LOG_FILE"
            else
                echo "  ✗ Failed to generate results for: $filename" | tee -a "$LOG_FILE"
            fi
            
            # Brief pause to manage system load
            sleep 1
        fi
    fi
done
