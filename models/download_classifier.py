# download MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7/ classifier from huggingface
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import os
print("📥 Downloading mDeBERTa-v3-base-xnli-multilingual-nli-2mil7...")
model = AutoModelForSequenceClassification.from_pretrained("MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")
tokenizer = AutoTokenizer.from_pretrained("MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")

# Save to mounted volume
output_path = "classifier/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
os.makedirs(output_path, exist_ok=True)
tokenizer.save_pretrained(output_path)
model.save_pretrained(output_path)  

print(f"✅ Saved to {output_path}")