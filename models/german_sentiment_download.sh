#!/bin/bash
# download_model_docker.sh
# Download emotion model using Docker instead of local Python

set -e

echo "============================================================================"
echo "📥 Downloading German-Emotions Model via Docker"
echo "============================================================================"
echo ""

# Create models directory if it doesn't exist
mkdir -p models/emotion

# Run download in Docker container with correct Python version
docker run -it --rm \
  -v "$(pwd)/models:/models" \
  -v "$(pwd)/scripts:/scripts" \
  -w /app \
  python:3.11-slim \
  bash -c "
    echo '📦 Installing dependencies...'
    pip install -q transformers==4.36.2 tokenizers==0.15.1 torch --index-url https://download.pytorch.org/whl/cpu
    
    echo ''
    echo '🔤 Downloading model from HuggingFace...'
    python << 'PYTHON_SCRIPT'
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from pathlib import Path

model_name = 'ChrisLalk/German-Emotions'
output_dir = Path('/emotion/german-emotions')
output_dir.mkdir(parents=True, exist_ok=True)

print(f'📁 Saving to: {output_dir}')
print('')

# Download tokenizer
print('🔤 Downloading tokenizer...')
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
tokenizer.save_pretrained(output_dir)
print('   ✅ Tokenizer saved')
print('')

# Download model
print('🤖 Downloading model...')
model = AutoModelForSequenceClassification.from_pretrained(
    model_name,
    torch_dtype=torch.float32
)
model.save_pretrained(output_dir)
print('   ✅ Model saved')
print('')

# Verify
import os
total_size = sum(
    os.path.getsize(os.path.join(root, f))
    for root, _, files in os.walk(output_dir)
    for f in files
)
print(f'📦 Total size: {total_size / (1024**2):.1f} MB')
print('')
print('✅ Download complete!')

PYTHON_SCRIPT
  "

echo ""
echo "============================================================================"
echo "✅ Model downloaded successfully!"
echo "============================================================================"
echo ""
echo "📁 Model location: models/emotion/german-emotions/"
echo ""
echo "Next steps:"
echo "  1. Verify files: ls -lh models/emotion/german-emotions/"
echo "  2. Build worker: docker compose build --no-cache emotion-worker"
echo "  3. Start worker: docker compose up -d emotion-worker"
echo ""