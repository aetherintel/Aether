
import os
from huggingface_hub import snapshot_download

MODEL_ID = "microsoft/Florence-2-large"
OUTPUT_PATH = "models/image/florence-2-large"

print(f"📥 Downloading {MODEL_ID} using snapshot_download...")

os.makedirs(OUTPUT_PATH, exist_ok=True)

# Download all files
snapshot_download(
    repo_id=MODEL_ID,
    local_dir=OUTPUT_PATH,
    local_dir_use_symlinks=False,  # Download actual files
    ignore_patterns=["*.msgpack", "*.h5", "*.tflite"] # Ignore other formats if any
)

print(f"✅ Saved to {OUTPUT_PATH}")

# Verify files
print("\n📁 Downloaded files:")
total_size = 0
for root, dirs, files in os.walk(OUTPUT_PATH):
    for f in files:
        fp = os.path.join(root, f)
        if os.path.isfile(fp):
            size = os.path.getsize(fp) / (1024**2)
            total_size += size
            # print(f"  - {f}: {size:.1f} MB")

print(f"📊 Total Size: {total_size:.1f} MB")