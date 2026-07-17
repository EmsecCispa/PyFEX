# merge_final_datasets.py
import os
import json
import random
from datetime import datetime

def load_json_data(filepath):
    """Load JSON data from a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None

def merge_sequence_data():
    """Merge malicious and benign sequence data"""
    print("Loading sequence data...")
    
    # Load malicious package data
    malicious_data = load_json_data("all_malware_sequences.json")
    if not malicious_data:
        return False
    
    # Load benign package data  
    benign_data = load_json_data("all_benign_sequences.json")
    if not benign_data:
        return False
    
    print(f"Malicious packages: {malicious_data['metadata']['total_packages']}")
    print(f"Benign packages: {benign_data['metadata']['total_packages']}")
    
    # Merge package data
    combined_packages = []
    
    # Add malicious packages (Label: 1)
    malicious_success = 0
    for package in malicious_data['packages']:
        if package['status'] == 'success' and package['sequence']:
            package['label'] = 1
            combined_packages.append(package)
            malicious_success += 1
    
    # Add benign packages (Label: 0)
    benign_success = 0
    for package in benign_data['packages']:
        if package['status'] == 'success' and package['sequence']:
            package['label'] = 0
            combined_packages.append(package)
            benign_success += 1
    
    # Create merged metadata
    combined_metadata = {
        'total_original_packages': malicious_data['metadata']['total_packages'] + benign_data['metadata']['total_packages'],
        'total_successful_packages': len(combined_packages),
        'malicious_original': malicious_data['metadata']['total_packages'],
        'malicious_successful': malicious_success,
        'malicious_success_rate': malicious_success / malicious_data['metadata']['total_packages'] * 100,
        'benign_original': benign_data['metadata']['total_packages'],
        'benign_successful': benign_success,
        'benign_success_rate': benign_success / benign_data['metadata']['total_packages'] * 100,
        'merged_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'description': 'Combined malicious and benign PyPI packages for malware detection'
    }
    
    # Save combined sequence data
    combined_data = {
        'metadata': combined_metadata,
        'packages': combined_packages
    }
    
    with open('combined_sequences.json', 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nCombined sequence data saved to: combined_sequences.json")
    print(f"Total successful packages: {len(combined_packages)}")
    print(f"  - Malicious: {malicious_success}")
    print(f"  - Benign: {benign_success}")
    
    return combined_packages

def merge_bert_training_data():
    """Merge BERT training data files"""
    print("\nMerging BERT training data...")
    
    # Read malicious training data
    malicious_lines = []
    if os.path.exists("bert_training_data.txt"):
        with open("bert_training_data.txt", 'r', encoding='utf-8') as f:
            malicious_lines = f.readlines()
    
    # Read benign training data
    benign_lines = []
    if os.path.exists("bert_training_data_benign.txt"):
        with open("bert_training_data_benign.txt", 'r', encoding='utf-8') as f:
            benign_lines = f.readlines()
    
    # Merge all data lines
    all_lines = malicious_lines + benign_lines
    
    # Save combined data
    with open("bert_training_data_combined.txt", 'w', encoding='utf-8') as f:
        f.writelines(all_lines)
    
    malicious_count = len(malicious_lines)
    benign_count = len(benign_lines)
    
    print(f"Combined BERT training data saved to: bert_training_data_combined.txt")
    print(f"Total samples: {len(all_lines)}")
    print(f"  - Malicious (Label 1): {malicious_count}")
    print(f"  - Benign (Label 0): {benign_count}")
    
    return all_lines, malicious_count, benign_count

def create_balanced_dataset(all_lines, malicious_count, benign_count):
    """Create a balanced dataset by undersampling the majority class"""
    print("\nCreating balanced dataset...")
    
    # Separate malicious and benign samples
    malicious_samples = [line for line in all_lines if line.startswith('1\t')]
    benign_samples = [line for line in all_lines if line.startswith('0\t')]
    
    print(f"Available malicious samples: {len(malicious_samples)}")
    print(f"Available benign samples: {len(benign_samples)}")
    
    # Use the smaller count as the baseline for balancing
    min_count = min(len(malicious_samples), len(benign_samples))
    
    # Randomly sample to achieve balance
    balanced_malicious = random.sample(malicious_samples, min_count)
    balanced_benign = random.sample(benign_samples, min_count)
    
    # Merge and shuffle the samples
    balanced_lines = balanced_malicious + balanced_benign
    random.shuffle(balanced_lines)
    
    # Save balanced dataset
    with open("bert_training_data_balanced.txt", 'w', encoding='utf-8') as f:
        f.writelines(balanced_lines)
    
    print(f"Balanced dataset saved to: bert_training_data_balanced.txt")
    print(f"Balanced samples: {len(balanced_lines)}")
    print(f"  - Malicious: {len(balanced_malicious)}")
    print(f"  - Benign: {len(balanced_benign)}")
    
    return balanced_lines

def create_dataset_stats():
    """Generate and save dataset statistics"""
    print("\nCreating dataset statistics...")
    
    stats = {}
    
    # Sequence data statistics
    if os.path.exists("combined_sequences.json"):
        with open("combined_sequences.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            stats['sequences'] = data['metadata']
    
    # BERT training data statistics
    bert_files = {
        'combined': 'bert_training_data_combined.txt',
        'balanced': 'bert_training_data_balanced.txt'
    }
    
    for name, filename in bert_files.items():
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                malicious = sum(1 for line in lines if line.startswith('1\t'))
                benign = sum(1 for line in lines if line.startswith('0\t'))
                
                stats[name] = {
                    'total_samples': len(lines),
                    'malicious_samples': malicious,
                    'benign_samples': benign,
                    'balance_ratio': min(malicious, benign) / max(malicious, benign) * 100 if max(malicious, benign) > 0 else 0
                }
    
    # Save statistics to JSON
    with open("dataset_statistics.json", 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"Dataset statistics saved to: dataset_statistics.json")
    
    # Print summary report
    print("\n" + "="*50)
    print("DATASET SUMMARY")
    print("="*50)
    
    if 'sequences' in stats:
        seq = stats['sequences']
        print(f"Sequences:")
        print(f"  Total packages: {seq['total_successful_packages']}")
        print(f"  Malicious: {seq['malicious_successful']} ({seq['malicious_success_rate']:.1f}% success rate)")
        print(f"  Benign: {seq['benign_successful']} ({seq['benign_success_rate']:.1f}% success rate)")
    
    for name in ['combined', 'balanced']:
        if name in stats:
            bert = stats[name]
            print(f"\n{name.upper()} BERT Data:")
            print(f"  Total samples: {bert['total_samples']}")
            print(f"  Malicious: {bert['malicious_samples']}")
            print(f"  Benign: {bert['benign_samples']}")
            print(f"  Balance: {bert['balance_ratio']:.1f}%")

def main():
    """Main execution function"""
    print("Starting final dataset merge...")
    print("="*60)
    
    # 1. Merge sequence data
    combined_packages = merge_sequence_data()
    if not combined_packages:
        print("Failed to merge sequence data")
        return
    
    # 2. Merge BERT training data
    all_lines, malicious_count, benign_count = merge_bert_training_data()
    
    # 3. Create balanced dataset
    if all_lines:
        create_balanced_dataset(all_lines, malicious_count, benign_count)
    
    # 4. Generate final statistics
    create_dataset_stats()
    
    print("\n" + "="*60)
    print("DATASET MERGE COMPLETED SUCCESSFULLY!")
    print("="*60)
    print("\nNext steps:")
    print("1. Use 'bert_training_data_balanced.txt' for training BERT model")
    print("2. Use 'combined_sequences.json' for analysis and debugging")
    print("3. Check 'dataset_statistics.json' for detailed statistics")

if __name__ == "__main__":
    main()
