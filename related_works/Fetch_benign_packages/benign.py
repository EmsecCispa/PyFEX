# extract_benign_sequences.py
import os
import sys
import ast
import json
import time
import glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

class SequenceExtractor:
    """
    Extract code behavior sequences from Python packages
    """
    
    def __init__(self):
        self.suspicious_keywords = {
            'os.system', 'os.popen', 'subprocess.call', 'subprocess.Popen',
            'eval', 'exec', 'compile', '__import__', 'input',
            'open', 'urllib.request.urlopen', 'requests.get', 'requests.post',
            'pickle.loads', 'marshal.loads', 'yaml.load',
            'system', 'popen', 'call', 'Popen'
        }
    
    def extract_function_calls_from_file(self, filepath):
        """
        Extract function calls from Python file using AST
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content)
            function_calls = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        function_calls.append(func_name)
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                        function_calls.append(func_name)
            
            return list(set(function_calls))
            
        except Exception as e:
            print(f"Parse file {filepath} failed: {e}")
            return []
    
    def extract_imports_from_file(self, filepath):
        """
        Extract imports from Python file
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                        if node.names:
                            for alias in node.names:
                                imports.append(f"{node.module}.{alias.name}")
            
            return list(set(imports))
            
        except Exception as e:
            print(f"Extract imports failed {filepath}: {e}")
            return []
    
    def find_python_files(self, package_path):
        """
        Recursively find all Python files in package directory
        """
        python_files = []
        
        for root, dirs, files in os.walk(package_path):
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(full_path)
                        python_files.append((full_path, file_size))
                    except OSError:
                        continue
        
        return python_files
    
    def analyze_package(self, package_path, package_name):
        """
        Analyze package and extract code behavior sequence
        """
        if not os.path.exists(package_path):
            print(f"Package path not exist: {package_path}")
            return ""
        
        python_files = self.find_python_files(package_path)
        
        if not python_files:
            print(f"No Python files found in: {package_name}")
            return ""
        
        # Sort by file size (largest first)
        python_files.sort(key=lambda x: x[1], reverse=True)
        
        # Always include setup.py if exists
        processed_files = []
        
        # Find setup.py
        setup_py_files = [f for f in python_files if os.path.basename(f[0]).lower() == 'setup.py']
        if setup_py_files:
            processed_files.append(setup_py_files[0][0])
        
        # Add other largest files (max 2 files total including setup.py)
        for file_path, file_size in python_files:
            if file_path not in processed_files and len(processed_files) < 2:
                processed_files.append(file_path)
        
        print(f"Processing {package_name}: {len(processed_files)} files")
        
        all_function_calls = []
        all_imports = []
        
        for py_file in processed_files:
            print(f"  Analyzing: {os.path.basename(py_file)}")
            function_calls = self.extract_function_calls_from_file(py_file)
            imports = self.extract_imports_from_file(py_file)
            
            all_function_calls.extend(function_calls)
            all_imports.extend(imports)
        
        # Remove duplicates
        all_function_calls = list(set(all_function_calls))
        all_imports = list(set(all_imports))
        
        # Build sequence: suspicious calls + imports + other calls
        suspicious_calls = [call for call in all_function_calls if call in self.suspicious_keywords]
        
        sequence_parts = []
        if suspicious_calls:
            sequence_parts.extend(suspicious_calls)
        if all_imports:
            sequence_parts.extend(all_imports)
        if all_function_calls:
            sequence_parts.extend([call for call in all_function_calls if call not in suspicious_calls])
        
        return " ".join(sequence_parts)

def process_single_package(package_info, extractor):
    """
    Process single package
    """
    package_path = package_info['path']
    package_name = package_info['name']
    
    print(f"Start processing: {package_name}")
    start_time = time.time()
    
    try:
        sequence = extractor.analyze_package(package_path, package_name)
        
        if sequence:
            end_time = time.time()
            sequence_length = len(sequence.split())
            print(f"SUCCESS: {package_name}, sequence length: {sequence_length}, time: {end_time - start_time:.2f}s")
            return {
                'name': package_name,
                'path': package_path,
                'sequence': sequence,
                'status': 'success'
            }
        else:
            print(f"NO_SEQUENCE: {package_name}")
            return {
                'name': package_name,
                'path': package_path,
                'sequence': '',
                'status': 'no_sequence'
            }
            
    except Exception as e:
        print(f"ERROR: {package_name} - {e}")
        return {
            'name': package_name,
            'path': package_path,
            'sequence': '',
            'status': 'error',
            'error': str(e)
        }

def discover_benign_packages():
    """
    Discover packages from benign packages directory
    """
    base_dir = "/home/john/pyforce/benign_packages"
    
    if not os.path.exists(base_dir):
        print(f"Benign packages directory not found: {base_dir}")
        return []
    
    all_packages = []
    
    print(f"Discovering packages in: {base_dir}")
    
    # Look for directories (extracted packages)
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        
        if os.path.isdir(item_path):
            # It's a directory, treat as package
            all_packages.append({
                'name': item,
                'path': item_path
            })
    
    return all_packages

def main():
    """
    Main function - process all benign packages with thread pool
    """
    # Configuration
    max_workers = 4
    output_file = "all_benign_sequences.json"
    
    # Discover packages from benign directory
    package_list = discover_benign_packages()
    
    if not package_list:
        print("No benign packages found")
        return
    
    print(f"Found {len(package_list)} benign packages")
    print("Starting sequence extraction...")
    print("=" * 60)
    
    # Create extractor
    extractor = SequenceExtractor()
    results = []
    
    # Process packages with thread pool
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_package = {
            executor.submit(process_single_package, pkg, extractor): pkg 
            for pkg in package_list
        }
        
        for i, future in enumerate(future_to_package):
            pkg = future_to_package[future]
            try:
                result = future.result(timeout=300)  # 5 minute timeout
                results.append(result)
                print(f"Progress: {i+1}/{len(package_list)}")
            except Exception as e:
                print(f"TIMEOUT: {pkg['name']} - {e}")
                results.append({
                    'name': pkg['name'],
                    'path': pkg['path'],
                    'sequence': '',
                    'status': 'timeout',
                    'error': str(e)
                })
    
    # Statistics
    successful = sum(1 for r in results if r['status'] == 'success')
    no_sequence = sum(1 for r in results if r['status'] == 'no_sequence')
    errors = sum(1 for r in results if r['status'] in ['error', 'timeout'])
    
    print("=" * 60)
    print("EXTRACTION COMPLETED:")
    print(f"  SUCCESS: {successful} packages")
    print(f"  NO_SEQUENCE: {no_sequence} packages") 
    print(f"  ERRORS/TIMEOUT: {errors} packages")
    
    # Save results
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'total_packages': len(package_list),
                'successful': successful,
                'no_sequence': no_sequence,
                'errors': errors,
                'type': 'benign',
                'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'packages': results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to: {output_file}")
    
    # Generate BERT training format for benign packages
    generate_bert_data(results)

def generate_bert_data(results):
    """
    Generate BERT training format data for benign packages
    """
    bert_file = "bert_training_data_benign.txt"
    
    with open(bert_file, 'w', encoding='utf-8') as f:
        for result in results:
            if result['status'] == 'success' and result['sequence']:
                # All benign packages get label 0
                label = 0
                f.write(f"{label}\t{result['sequence']}\n")
    
    print(f"BERT training data for benign packages saved to: {bert_file}")
    
    # Create detailed mapping file
    mapping_file = "package_mapping_benign.json"
    mapping_data = {}
    
    for result in results:
        if result['status'] == 'success' and result['sequence']:
            mapping_data[result['name']] = {
                'sequence_length': len(result['sequence'].split()),
                'status': result['status']
            }
    
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, indent=2, ensure_ascii=False)
    
    print(f"Benign package mapping saved to: {package_mapping_benign.json}")

if __name__ == "__main__":
    main()