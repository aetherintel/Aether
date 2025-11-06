#!/bin/bash
# scripts/init_models.sh - FIXED für Docker Volumes

set -e

echo "═══════════════════════════════════════════════════════════════════"
echo "🚀 AI Model Initialization (Docker Volumes)"
echo "═══════════════════════════════════════════════════════════════════"

COMPOSE_CMD="docker compose"
command -v docker-compose &> /dev/null && COMPOSE_CMD="docker-compose"

COMPOSE_FILE="${1:-docker-compose.prod.yml}"
LOG_DIR="./logs/model-init"
mkdir -p "$LOG_DIR"

# ═══════════════════════════════════════════════════════════════════════
# Helper: Check if volume has models
# ═══════════════════════════════════════════════════════════════════════
check_volume_initialized() {
  local volume_name=$1
  local min_files=${2:-3}
  
  if ! docker volume ls | grep -q "$volume_name"; then
    return 1
  fi
  
  file_count=$(docker run --rm -v ${volume_name}:/check alpine:latest \
    sh -c 'find /check -type f 2>/dev/null | wc -l')
  
  [ "$file_count" -ge "$min_files" ]
}

# ═══════════════════════════════════════════════════════════════════════
# Translation Models
# ═══════════════════════════════════════════════════════════════════════
init_translation() {
  echo ""
  echo "═══ Translation Worker ═══"
  
  if check_volume_initialized "app_translation_models" 5; then
    echo "✅ Models exist, skipping"
    return 0
  fi
  
  echo "📥 Downloading M2M-100 (~1.5GB)..."
  
  $COMPOSE_CMD -f $COMPOSE_FILE run --rm \
    -v app_translation_models:/models \
    --entrypoint python \
    translation-worker -c '
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
import torch

print("Downloading M2M-100...")
model = M2M100ForConditionalGeneration.from_pretrained(
    "facebook/m2m100_418M",
    cache_dir="/models",
    torch_dtype=torch.float32
)
tokenizer = M2M100Tokenizer.from_pretrained(
    "facebook/m2m100_418M",
    cache_dir="/models"
)
print("✅ Translation models ready")
' 2>&1 | tee "$LOG_DIR/translation.log"
}

# ═══════════════════════════════════════════════════════════════════════
# Audio Models (Whisper)
# ═══════════════════════════════════════════════════════════════════════
init_audio() {
  echo ""
  echo "═══ Audio Worker (Whisper) ═══"
  
  if check_volume_initialized "app_audio_models" 3; then
    echo "✅ Models exist, skipping"
    return 0
  fi
  
  echo "📥 Downloading Whisper base (~150MB)..."
  
  $COMPOSE_CMD -f $COMPOSE_FILE run --rm \
    -v app_audio_models:/models \
    --entrypoint python \
    audio-worker -c '
import whisper
import os

os.environ["WHISPER_CACHE"] = "/models"
print("Downloading Whisper base...")
model = whisper.load_model("base", download_root="/models")
print("✅ Audio models ready")
' 2>&1 | tee "$LOG_DIR/audio.log"
}

# ═══════════════════════════════════════════════════════════════════════
# Emotion Models
# ═══════════════════════════════════════════════════════════════════════
init_emotion() {
  echo ""
  echo "═══ Emotion Worker ═══"
  
  if check_volume_initialized "app_emotion_models" 3; then
    echo "✅ Models exist, skipping"
    return 0
  fi
  
  echo "📥 Downloading German-Emotions..."
  
  $COMPOSE_CMD -f $COMPOSE_FILE run --rm \
    -v app_emotion_models:/models \
    --entrypoint python \
    emotion-worker -c '
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_name = "ChrisLalk/German-Emotions"
print(f"Downloading {model_name}...")
tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir="/models")
model = AutoModelForSequenceClassification.from_pretrained(
    model_name,
    cache_dir="/models",
    torch_dtype=torch.float32
)
print("✅ Emotion models ready")
' 2>&1 | tee "$LOG_DIR/emotion.log"
}

# ═══════════════════════════════════════════════════════════════════════
# Image Models (EasyOCR)
# ═══════════════════════════════════════════════════════════════════════
init_image() {
  echo ""
  echo "═══ Image Worker (OCR) ═══"
  
  if check_volume_initialized "app_image_models" 3; then
    echo "✅ Models exist, skipping"
    return 0
  fi
  
  echo "📥 Downloading EasyOCR (~150MB)..."
  
  $COMPOSE_CMD -f $COMPOSE_FILE run --rm \
    -v app_image_models:/models \
    --entrypoint python \
    image-worker -c '
import easyocr
import os

os.environ["EASYOCR_MODULE_PATH"] = "/models"
print("Downloading EasyOCR models...")
reader = easyocr.Reader(
    ["en", "de"],
    model_storage_directory="/models",
    download_enabled=True,
    gpu=False
)
print("✅ Image models ready")
' 2>&1 | tee "$LOG_DIR/image.log"
}

# ═══════════════════════════════════════════════════════════════════════
# Classification Models
# ═══════════════════════════════════════════════════════════════════════
init_classification() {
  echo ""
  echo "═══ Classification Worker ═══"
  
  if check_volume_initialized "app_classifier_models" 3; then
    echo "✅ Models exist, skipping"
    return 0
  fi
  
  echo "📥 Downloading mDeBERTa..."
  
  $COMPOSE_CMD -f $COMPOSE_FILE run --rm \
    -v app_classifier_models:/models \
    --entrypoint python \
    classification-worker -c '
from transformers import AutoTokenizer, AutoModelForSequenceClassification

model_name = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
print(f"Downloading {model_name}...")
tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir="/models")
model = AutoModelForSequenceClassification.from_pretrained(
    model_name,
    cache_dir="/models"
)
print("✅ Classification models ready")
' 2>&1 | tee "$LOG_DIR/classification.log"
}

# ═══════════════════════════════════════════════════════════════════════
# Geolocation (spaCy - pre-installed)
# ═══════════════════════════════════════════════════════════════════════
init_geolocation() {
  echo ""
  echo "═══ Geolocation Worker ═══"
  echo "✅ spaCy models pre-installed in image"
}

# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════
main() {
  echo ""
  echo "📋 Initializing AI models in Docker volumes..."
  echo "⚠️  This may take 10-30 minutes on first run"
  echo ""
  
  init_translation &
  PID_TRANS=$!
  
  sleep 10  # Stagger starts
  
  init_audio &
  PID_AUDIO=$!
  
  sleep 10
  
  init_emotion &
  PID_EMOTION=$!
  
  sleep 10
  
  init_image &
  PID_IMAGE=$!
  
  sleep 10
  
  init_classification &
  PID_CLASS=$!
  
  init_geolocation
  
  echo ""
  echo "⏳ Waiting for downloads to complete..."
  
  wait $PID_TRANS && echo "✅ Translation done" || echo "❌ Translation failed"
  wait $PID_AUDIO && echo "✅ Audio done" || echo "❌ Audio failed"
  wait $PID_EMOTION && echo "✅ Emotion done" || echo "❌ Emotion failed"
  wait $PID_IMAGE && echo "✅ Image done" || echo "❌ Image failed"
  wait $PID_CLASS && echo "✅ Classification done" || echo "❌ Classification failed"
  
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "✅ Model initialization complete!"
  echo "📁 Logs: $LOG_DIR/"
  echo ""
  echo "💾 Volume usage:"
  docker volume ls | grep "app_.*_models"
  echo "════════════════════════════════════════════════════════════════"
}

main