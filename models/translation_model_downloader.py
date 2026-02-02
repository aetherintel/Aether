from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os

MODEL_ID = "facebook/nllb-200-distilled-600M"
OUTPUT_PATH = "translation/nllb-200-distilled-600M"

print(f"📥 Downloading {MODEL_ID}...")

# Download to a FRESH directory - load using Auto classes
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID)

# Save to mounted volume
os.makedirs(OUTPUT_PATH, exist_ok=True)

print(f"💾 Saving to {OUTPUT_PATH}...")
tokenizer.save_pretrained(OUTPUT_PATH)
model.save_pretrained(OUTPUT_PATH)

print(f"✅ Saved to {OUTPUT_PATH}")

# Verify files
import json
try:
    with open(f"{OUTPUT_PATH}/tokenizer_config.json", 'r') as f:
        config = json.load(f)
        print("✅ tokenizer_config.json is valid JSON")
except Exception as e:
    print(f"❌ Verification failed: {e}")

print("\n📁 Downloaded files:")
total_size = 0
for f in os.listdir(OUTPUT_PATH):
    fp = f"{OUTPUT_PATH}/{f}"
    if os.path.isfile(fp):
        size = os.path.getsize(fp) / (1024**2)
        total_size += size
        print(f"  - {f}: {size:.1f} MB")

print(f"📊 Total Size: {total_size:.1f} MB")