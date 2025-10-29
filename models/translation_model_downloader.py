from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
import os

print("📥 Downloading M2M-100-418M...")

# Download to a FRESH directory
tokenizer = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")
model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")

# Save to mounted volume
output_path = "translation/m2m100_418M"
os.makedirs(output_path, exist_ok=True)

tokenizer.save_pretrained(output_path)
model.save_pretrained(output_path)

print(f"✅ Saved to {output_path}")

# Verify files
import json
with open(f"{output_path}/tokenizer_config.json", 'r') as f:
    config = json.load(f)
    print("✅ tokenizer_config.json is valid JSON")

print("\n📁 Downloaded files:")
for f in os.listdir(output_path):
    size = os.path.getsize(f"{output_path}/{f}") / (1024**2)
    print(f"  - {f}: {size:.1f} MB")