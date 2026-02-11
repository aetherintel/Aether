from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from pathlib import Path
import os

def download_emotion_model():
    print("📥 Downloading German-Emotions Model...")
    
    model_name = 'ChrisLalk/German-Emotions'
    # Output path matches where the worker expects it (or where we copy from)
    output_dir = Path('./emotion/german-emotions')
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f'📁 Saving to: {output_dir}')

    # Download tokenizer
    print('🔤 Downloading tokenizer...')
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
    tokenizer.save_pretrained(output_dir)
    print('   ✅ Tokenizer saved')

    # Download model
    print('🤖 Downloading model...')
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        torch_dtype=torch.float32
    )
    model.save_pretrained(output_dir)
    print('   ✅ Model saved')

    # Verify
    total_size = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(output_dir)
        for f in files
    )
    print(f'📦 Total size: {total_size / (1024**2):.1f} MB')

if __name__ == "__main__":
    download_emotion_model()
