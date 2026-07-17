import json
import csv
import os
from pathlib import Path
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def extract_package_name(filename: str) -> str:
    """Extracts the package name from the filename by removing prefix and suffix."""
    if filename.startswith("analysis_"):
        filename = filename[len("analysis_"):]
    if filename.endswith(".json"):
        filename = filename[:-len(".json")]
    return filename

def load_json_files(directory: str) -> List[Dict[str, Any]]:
    """Loads all JSON files from a directory and extracts relevant data."""
    json_dir = Path(directory)
    json_files = list(json_dir.glob("*.json"))
    
    all_data = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract package name from the filename for verification
            package_name_from_file = extract_package_name(json_file.name)
            data['package_name_from_file'] = package_name_from_file
            
            all_data.append(data)
            
        except Exception as e:
            logging.error(f"Error processing {json_file}: {e}")
    
    return all_data

def create_csv_output(data: List[Dict[str, Any]], output_file: str):
    """Consolidates JSON data into a structured CSV file."""
    
    # Predefined detection vectors based on security analysis requirements
    all_detection_vectors = [
        "version_mismatch",
        "suspicious_timing", 
        "file_type_anomaly",
        "naming_suspicion",
        "code_obfuscation",
        "structure_anomaly",
        "js_malicious_code",
        "metadata_tampering",
        "dependency_confusion",
        "license_violation"
    ]
    
    # Define CSV column structure
    fieldnames = [
        'package_name_from_file',
        'package_name_from_json',
        'malicious_score', 
        'risk_level',
        'confidence',
        'reasoning'
    ]
    
    # Append binary flag columns for each vector
    for vector in all_detection_vectors:
        fieldnames.append(f"has_{vector}")
    
    fieldnames.append('detection_vectors_count')
    fieldnames.append('detection_vectors_list')
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in data:
            row = {
                'package_name_from_file': item.get('package_name_from_file', ''),
                'package_name_from_json': item.get('package_name', ''),
                'malicious_score': item.get('malicious_score', -1),
                'risk_level': item.get('risk_level', 'unknown'),
                'confidence': item.get('confidence', 0.0),
                'reasoning': item.get('reasoning', '')
            }
            
            # Handle list of detection vectors
            vectors = item.get('detection_vectors', [])
            if not isinstance(vectors, list): # Safety check
                vectors = []
                
            row['detection_vectors_count'] = len(vectors)
            row['detection_vectors_list'] = ';'.join(vectors)
            
            # Populate binary columns
            for vector in all_detection_vectors:
                row[f"has_{vector}"] = 1 if vector in vectors else 0
            
            writer.writerow(row)
    
    logging.info(f"CSV file created successfully: {output_file}")

def main():
    # Configuration
    JSON_DIR = "Analysis_Results"
    OUTPUT_CSV = "pypi_malware_analysis.csv"
    
    if not os.path.exists(JSON_DIR):
        logging.error(f"Directory does not exist: {JSON_DIR}")
        return

    logging.info("Starting to load JSON files...")
    data = load_json_files(JSON_DIR)
    
    if not data:
        logging.warning("No data found to process.")
        return

    logging.info(f"Successfully loaded {len(data)} JSON files.")
    
    # Create CSV file
    logging.info("Starting CSV generation...")
    create_csv_output(data, OUTPUT_CSV)
    
    # Statistical Summary
    malicious_scores = [item.get('malicious_score', -1) for item in data]
    risk_levels = [item.get('risk_level', 'unknown') for item in data]
    
    logging.info("=" * 50)
    logging.info("ANALYSIS STATISTICS:")
    logging.info(f"Malicious Score Range: {min(malicious_scores)} to {max(malicious_scores)}")
    
    risk_counts = {}
    for risk in risk_levels:
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
    
    for risk, count in risk_counts.items():
        percentage = (count / len(data)) * 100
        logging.info(f"{risk}: {count} ({percentage:.2f}%)")
    
    logging.info(f"CSV file saved to: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
