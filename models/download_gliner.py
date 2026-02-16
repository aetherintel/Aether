import os
import shutil
from gliner import GLiNER

# Model to download
MODEL_NAME = "urchade/gliner_medium-v2.1"
OUTPUT_DIR = "models/geolocation/gliner_model"

print(f"Downloading {MODEL_NAME}...")

# Load model (downloads to cache)
model = GLiNER.from_pretrained(MODEL_NAME)

# Save to specific directory
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
    
model.save_pretrained(OUTPUT_DIR)

print(f"Model saved to {OUTPUT_DIR}")
