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
    """Extract package name from filename by removing 'analysis_' prefix and '.json' suffix"""
    if filename.startswith("analysis_"):
        filename = filename[len("analysis_"):]
    if filename.endswith(".json"):
        filename = filename[:-len(".json")]
    return filename

def load_json_files(directory: str) -> List[Dict[str, Any]]:
    """Load all JSON files from the directory and extract data"""
    json_dir = Path(directory)
    json_files = list(json_dir.glob("*.json"))
    
    all_data = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract package name from filename
            package_name_from_file = extract_package_name(json_file.name)
            
            # Ensure the data contains the package name extracted from the file
            data['package_name_from_file'] = package_name_from_file
            
            all_data.append(data)
            
        except Exception as e:
            logging.error(f"Error processing {json_file}: {e}")
    
    return all_data

def create_csv_output(data: List[Dict[str, Any]], output_file: str):
    """Create a consolidated CSV output file"""
    
    # Define all possible detection vectors
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
    
    # CSV Column definitions
    fieldnames = [
        'package_name_from_file',
        'package_name_from_json',
        'malicious_score', 
        'risk_level',
        'confidence',
        'reasoning'
    ]
    
    # Add each detection vector as an individual binary column
    for vector in all_detection_vectors:
        fieldnames.append(f"has_{vector}")
    
    # Add summary columns for detection vectors
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
            
            # Process detection vectors
            detection_vectors = item.get('detection_vectors', [])
            # Handle cases where LLM might return a non-list
            if not isinstance(detection_vectors, list):
                detection_vectors = []
                
            detection_vectors_count = len(detection_vectors)
            detection_vectors_list = ';'.join(detection_vectors)
            
            row['detection_vectors_count'] = detection_vectors_count
            row['detection_vectors_list'] = detection_vectors_list
            
            # Create binary indicators for each detection vector
            for vector in all_detection_vectors:
                row[f"has_{vector}"] = 1 if vector in detection_vectors else 0
            
            writer.writerow(row)
    
    logging.info(f"CSV file successfully created: {output_file}")

def main():
    # Configuration parameters
    JSON_DIR = "Analysis_Results"  # Directory containing JSON files
    OUTPUT_CSV = "pypi_malware_analysis.csv"  # Output CSV filename
    
    # Check if directory exists
    if not os.path.exists(JSON_DIR):
        logging.error(f"Directory not found: {JSON_DIR}")
        return
    
    # Load JSON data
    logging.info("Starting to load JSON files...")
    data = load_json_files(JSON_DIR)
    
    if not data:
        logging.warning("No data found to process.")
        return
        
    logging.info(f"Successfully loaded {len(data)} JSON files")
    
    # Create CSV file
    logging.info("Generating CSV output...")
    create_csv_output(data, OUTPUT_CSV)
    
    # Generate statistics
    malicious_scores = [item.get('malicious_score', -1) for item in data if isinstance(item.get('malicious_score'), (int, float))]
    risk_levels = [item.get('risk_level', 'unknown') for item in data]
    
    logging.info("=" * 50)
    logging.info("ANALYSIS STATISTICS")
    logging.info("=" * 50)
    
    if malicious_scores:
        logging.info(f"Malicious Score Range: {min(malicious_scores)} - {max(malicious_scores)}")
    
    risk_counts = {}
    for risk in risk_levels:
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
    
    logging.info("Risk Level Distribution:")
    for risk, count in risk_counts.items():
        percentage = (count / len(data)) * 100
        logging.info(f"  - {risk}: {count} ({percentage:.2f}%)")
    
    logging.info("=" * 50)
    logging.info(f"CSV file saved as: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
