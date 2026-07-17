# bert_train_final.py
import torch
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from transformers import EarlyStoppingCallback
from sklearn.model_selection import train_test_split
from datasets import Dataset
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
import json

def load_data(data_path):
    """Load training data from a TSV-style text file"""
    data = []
    labels = []
    
    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 2:
                label, sequence = parts
                data.append(sequence)
                labels.append(int(label))
    
    return data, labels

def compute_metrics(eval_pred):
    """Calculate evaluation metrics for the model"""
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    
    # Calculate standard metrics
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average='binary')
    acc = accuracy_score(labels, predictions)
    
    # Add detailed metrics for each class (benign vs malicious)
    class_report = classification_report(labels, predictions, output_dict=True, target_names=['benign', 'malicious'])
    
    return {
        'accuracy': acc,
        'f1': f1,
        'precision': precision,
        'recall': recall,
        'malicious_precision': class_report['malicious']['precision'],
        'malicious_recall': class_report['malicious']['recall'],
        'malicious_f1': class_report['malicious']['f1-score'],
        'benign_precision': class_report['benign']['precision'],
        'benign_recall': class_report['benign']['recall'],
        'benign_f1': class_report['benign']['f1-score'],
    }

def main():
    # Configuration
    model_name = "bert-base-uncased"
    data_file = "bert_training_data_balanced.txt"  # Using the balanced dataset from previous step
    output_dir = "./bert_final_model"
    
    print("Loading training data...")
    sequences, labels = load_data(data_file)
    
    print(f"Total samples loaded: {len(sequences)}")
    label_counts = pd.Series(labels).value_counts()
    print(f"Label distribution: {label_counts.to_dict()}")
    
    # Split data (80% Training, 20% Validation)
    # Using 'stratify' to ensure class balance is maintained in both sets
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        sequences, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print(f"Training samples: {len(train_texts)}")
    print(f"Validation samples: {len(val_texts)}")
    
    # Initialize the tokenizer
    tokenizer = BertTokenizer.from_pretrained(model_name)
    
    # Tokenization helper function
    def tokenize_function(examples):
        return tokenizer(examples['text'], padding="max_length", truncation=True, max_length=512)
    
    # Create Dataset objects
    train_dataset = Dataset.from_dict({"text": train_texts, "labels": train_labels})
    val_dataset = Dataset.from_dict({"text": val_texts, "labels": val_labels})
    
    # Map tokenization across datasets
    print("Tokenizing datasets...")
    train_dataset = train_dataset.map(tokenize_function, batched=True)
    val_dataset = val_dataset.map(tokenize_function, batched=True)
    
    # Set PyTorch format
    train_dataset.set_format(type='torch', columns=['input_ids', 'attention_mask', 'labels'])
    val_dataset.set_format(type='torch', columns=['input_ids', 'attention_mask', 'labels'])
    
    # Load model for sequence classification
    num_labels = len(set(labels))
    print(f"Initializing model with {num_labels} classes...")
    
    model = BertForSequenceClassification.from_pretrained(
        model_name, 
        num_labels=num_labels
    )
    
    # Define Training Arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=4,              # Number of training epochs
        per_device_train_batch_size=16,  # Batch size per device
        per_device_eval_batch_size=16,
        warmup_steps=500,                # Linear warmup phase
        weight_decay=0.01,               # Regularization
        logging_dir='./logs',
        logging_steps=50,
        evaluation_strategy="steps",
        eval_steps=100,
        save_steps=200,
        load_best_model_at_end=True,     # Keep the best model based on metrics
        metric_for_best_model="f1",
        greater_is_better=True,
        save_total_limit=3,              # Keep only the top 3 checkpoints
        report_to=None,                  # Disable external reporting (e.g., wandb)
    )
    
    # Initialize the Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)], # Stop if metric doesn't improve
    )
    
    # Start the training process
    print("\n" + "="*30)
    print("STARTING TRAINING")
    print("="*30)
    train_result = trainer.train()
    
    # Save the final model and tokenizer
    trainer.save_model()
    tokenizer.save_pretrained(output_dir)
    
    # Save training metrics
    metrics = train_result.metrics
    with open(f"{output_dir}/training_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\nModel training completed. Saved to: {output_dir}")
    
    # Final evaluation on the validation set
    print("\n" + "="*30)
    print("FINAL EVALUATION")
    print("="*30)
    eval_results = trainer.evaluate()
    for key, value in eval_results.items():
        print(f"  {key}: {value:.4f}")
    
    # Save final evaluation results
    with open(f"{output_dir}/evaluation_results.json", "w") as f:
        json.dump(eval_results, f, indent=2)

if __name__ == "__main__":
    main()
