#!/bin/bash
# scripts/init_models.sh
# Sequential model initialization and download manager
# Triggers model downloads for all AI workers without blocking deployment

set -e

echo "═══════════════════════════════════════════════════════════════════"
echo "🚀 AI Worker Model Initialization Manager"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "📋 This script will initialize models for all AI workers sequentially"
echo "⚡ Models will be downloaded in background if not present"
echo ""

# Configuration
LOG_DIR="./logs/model-downloads"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAIN_LOG="$LOG_DIR/init_${TIMESTAMP}.log"

# Docker Compose command
if command -v docker-compose &> /dev/null; then
  COMPOSE_CMD="docker-compose"
else
  COMPOSE_CMD="docker compose"
fi

# Determine which compose file to use
COMPOSE_FILE="${1:-docker-compose.prod.yml}"

echo "📝 Logs will be written to: $LOG_DIR"
echo "🐳 Using compose file: $COMPOSE_FILE"
echo ""

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ℹ️  $1" | tee -a "$MAIN_LOG"
}

log_success() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1" | tee -a "$MAIN_LOG"
}

log_error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1" | tee -a "$MAIN_LOG"
}

log_warning() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  $1" | tee -a "$MAIN_LOG"
}

# Check if a model directory exists and has files
check_model_exists() {
  local model_path=$1
  if [ -d "$model_path" ] && [ "$(ls -A $model_path 2>/dev/null)" ]; then
    return 0  # Model exists
  else
    return 1  # Model doesn't exist
  fi
}

# Trigger model download for a specific worker
trigger_model_download() {
  local worker_name=$1
  local model_path=$2
  local download_command=$3
  local log_file="$LOG_DIR/${worker_name}_${TIMESTAMP}.log"
  
  log_info "[$worker_name] Checking model at: $model_path"
  
  if check_model_exists "$model_path"; then
    log_success "[$worker_name] Model already present, skipping download"
    return 0
  fi
  
  log_info "[$worker_name] Model not found, triggering download..."
  log_info "[$worker_name] Log file: $log_file"
  
  # Run download command in background
  {
    echo "═══════════════════════════════════════════════════════════════════" > "$log_file"
    echo "🔽 Model Download for: $worker_name" >> "$log_file"
    echo "⏰ Started: $(date)" >> "$log_file"
    echo "═══════════════════════════════════════════════════════════════════" >> "$log_file"
    echo "" >> "$log_file"
    
    eval "$download_command" >> "$log_file" 2>&1
    local exit_code=$?
    
    echo "" >> "$log_file"
    echo "═══════════════════════════════════════════════════════════════════" >> "$log_file"
    echo "⏰ Finished: $(date)" >> "$log_file"
    echo "📊 Exit Code: $exit_code" >> "$log_file"
    echo "═══════════════════════════════════════════════════════════════════" >> "$log_file"
    
    if [ $exit_code -eq 0 ]; then
      log_success "[$worker_name] Model download completed successfully"
    else
      log_error "[$worker_name] Model download failed with exit code $exit_code"
    fi
  } &
  
  local download_pid=$!
  log_info "[$worker_name] Download running in background (PID: $download_pid)"
  
  # Wait a moment before starting next download to avoid resource contention
  sleep 5
  
  return 0
}

# Wait for all background jobs
wait_for_downloads() {
  log_info "⏳ Waiting for all model downloads to complete..."
  wait
  log_success "All model downloads finished (check individual logs for status)"
}

# ============================================================================
# Model Download Definitions
# ============================================================================

initialize_translation_models() {
  log_info "═══ 1/6 Translation Worker (M2M-100) ═══"
  
  trigger_model_download \
    "translation-worker" \
    "./models/translation/m2m100_418M" \
    "$COMPOSE_CMD -f $COMPOSE_FILE run --rm --no-deps translation-worker python -c '
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
import torch
print(\"Downloading M2M-100 model (~1.5GB)...\")
model = M2M100ForConditionalGeneration.from_pretrained(\"facebook/m2m100_418M\", torch_dtype=torch.float32)
tokenizer = M2M100Tokenizer.from_pretrained(\"facebook/m2m100_418M\")
model.save_pretrained(\"/app/models/translation/m2m100_418M\")
tokenizer.save_pretrained(\"/app/models/translation/m2m100_418M\")
print(\"✅ M2M-100 model downloaded!\")
'"
}

initialize_image_models() {
  log_info "═══ 2/6 Image Worker (EasyOCR) ═══"
  
  trigger_model_download \
    "image-worker" \
    "./models/image/easyocr" \
    "$COMPOSE_CMD -f $COMPOSE_FILE run --rm --no-deps image-worker python -c '
import easyocr
from pathlib import Path
model_dir = Path(\"/app/models/image/easyocr\")
model_dir.mkdir(parents=True, exist_ok=True)
print(\"Downloading EasyOCR models (~150MB)...\")
reader = easyocr.Reader([\"en\", \"de\", \"fr\", \"it\", \"es\"], model_storage_directory=str(model_dir), download_enabled=True, gpu=False)
print(\"✅ EasyOCR models downloaded!\")
'"
}

initialize_audio_models() {
  log_info "═══ 3/6 Audio Worker (Whisper) ═══"
  
  trigger_model_download \
    "audio-worker" \
    "./models/audio/whisper" \
    "$COMPOSE_CMD -f $COMPOSE_FILE run --rm --no-deps audio-worker python -c '
import whisper
import os
print(\"Downloading Whisper base model (~150MB)...\")
model = whisper.load_model(\"base\", download_root=\"/app/models/audio/whisper\")
print(\"✅ Whisper model downloaded!\")
'"
}

initialize_emotion_models() {
  log_info "═══ 4/6 Emotion Worker (German-Emotions) ═══"
  
  trigger_model_download \
    "emotion-worker" \
    "./models/emotion/german-emotions" \
    "$COMPOSE_CMD -f $COMPOSE_FILE run --rm --no-deps emotion-worker python -c '
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from pathlib import Path
model_name = \"ChrisLalk/German-Emotions\"
output_dir = Path(\"/app/models/emotion/german-emotions\")
output_dir.mkdir(parents=True, exist_ok=True)
print(f\"Downloading {model_name} model...\")
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
model = AutoModelForSequenceClassification.from_pretrained(model_name, torch_dtype=torch.float32)
tokenizer.save_pretrained(output_dir)
model.save_pretrained(output_dir)
print(\"✅ Emotion model downloaded!\")
'"
}

initialize_classification_models() {
  log_info "═══ 5/6 Classification Worker ═══"
  
  trigger_model_download \
    "classification-worker" \
    "./models/classifier" \
    "$COMPOSE_CMD -f $COMPOSE_FILE run --rm --no-deps classification-worker python -c '
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from pathlib import Path
# Replace with your actual classification model
model_name = \"mDeBERTa-v3-base-xnli-multilingual-nli-2mil7\"  # Update this!
output_dir = Path(\"/app/models/classifier\")
output_dir.mkdir(parents=True, exist_ok=True)
print(f\"Downloading {model_name} model...\")
try:
    model = AutoModelForSequenceClassification.from_pretrained("MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")
    tokenizer = AutoTokenizer.from_pretrained("MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")
    tokenizer.save_pretrained(output_dir)
    model.save_pretrained(output_dir)
    print(\"✅ Classification model downloaded!\")
except Exception as e:
    print(f\"⚠️  Classification model download skipped: {e}\")
'"
}

initialize_geolocation_models() {
  log_info "═══ 6/6 Geolocation Worker (spaCy) ═══"
  
  trigger_model_download \
    "geolocation-worker" \
    "./models/geolocation" \
    "$COMPOSE_CMD -f $COMPOSE_FILE run --rm --no-deps geolocation-worker python -c '
import spacy
from pathlib import Path
print(\"Verifying spaCy model...\")
try:
    nlp = spacy.load(\"de_core_news_sm\")
    print(\"✅ spaCy model already available!\")
except:
    print(\"⚠️  spaCy model not found, should be installed via requirements.txt\")
'"
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
  log_info "Starting sequential model initialization..."
  echo ""
  
  # Initialize each worker's models sequentially
  initialize_translation_models
  initialize_image_models
  initialize_audio_models
  initialize_emotion_models
  initialize_classification_models
  initialize_geolocation_models
  
  echo ""
  log_success "All model download jobs have been triggered!"
  echo ""
  echo "════════════════════════════════════════════════════════════════════"
  echo "📊 Summary:"
  echo "════════════════════════════════════════════════════════════════════"
  echo "✅ 6 model initialization jobs triggered"
  echo "📁 Log directory: $LOG_DIR"
  echo "📝 Main log: $MAIN_LOG"
  echo ""
  echo "💡 Models are downloading in the background"
  echo "💡 Workers will use models once downloads complete"
  echo "💡 Check individual log files for download progress"
  echo ""
  echo "🔍 Monitor progress:"
  echo "   tail -f $LOG_DIR/*_${TIMESTAMP}.log"
  echo ""
  echo "📊 Check disk usage:"
  echo "   du -sh ./models/*"
  echo ""
  echo "════════════════════════════════════════════════════════════════════"
}

# Run main function
main

# Optional: Wait for all downloads (comment out if you don't want to wait)
# wait_for_downloads

exit 0