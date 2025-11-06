#!/bin/bash
# setup_models_on_vm.sh

set -e

echo "🚀 Setting up models on VM (one-time)"

# SSH Config
VM_HOST=""
SSH_KEY=""
VM_APP_DIR="~/app"

# Check if we're in the right directory
if [ ! -d "models" ]; then
  echo "❌ Error: models/ directory not found"
  echo "📁 Current directory: $(pwd)"
  echo ""
  echo "💡 Please run this script from your project root where models/ exists"
  echo "   Example: cd ~/path/to/Aether && ./setup_models_on_vm.sh"
  exit 1
fi

# Test SSH connection
echo "🔐 Testing SSH connection..."
ssh -i ${SSH_KEY} ${VM_HOST} "echo '✅ SSH connected'"

# Create app directory on VM if not exists
echo "📁 Creating app directory on VM..."
ssh -i ${SSH_KEY} ${VM_HOST} "mkdir -p ${VM_APP_DIR}"

# 1. Upload Models
echo ""
echo "📤 Uploading models to VM (~5 GB, 10-20 min)..."
echo "📂 Source: $(pwd)/models/"
echo "📂 Destination: ${VM_HOST}:${VM_APP_DIR}/models/"
echo ""

rsync -avz --progress -e "ssh -i ${SSH_KEY}" \
  models/ \
  ${VM_HOST}:${VM_APP_DIR}/models/

# 2. Populate Docker Volumes
echo ""
echo "📦 Creating and populating Docker volumes..."
ssh -i ${SSH_KEY} ${VM_HOST} << 'REMOTE'
cd ~/app

echo "Creating volumes..."

# Helper function
populate_volume() {
  local volume_name=$1
  local source_path=$2
  
  echo "  → $volume_name"
  
  # Create volume if not exists
  docker volume create $volume_name 2>/dev/null || true
  
  # Check if source exists
  if [ ! -d "models/$source_path" ]; then
    echo "    ⚠️  Warning: models/$source_path not found, skipping"
    return
  fi
  
  # Populate volume
  docker run --rm \
    -v $(pwd)/models/$source_path:/src:ro \
    -v $volume_name:/dest \
    alpine sh -c "rm -rf /dest/* && cp -r /src/* /dest/ && echo '    ✅ Copied $(du -sh /dest | cut -f1)'"
}

# Populate all model volumes
populate_volume app_translation_models translation/m2m100_418M
populate_volume app_audio_models audio/whisper
populate_volume app_emotion_models emotion/german-emotions
populate_volume app_image_models image/easyocr
populate_volume app_classifier_models classifier/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
populate_volume app_geolocation_models geolocation/geonames

echo ""
echo "✅ All volumes populated!"
echo ""
echo "📊 Volume sizes:"
for vol in app_translation_models app_audio_models app_emotion_models app_image_models app_classifier_models app_geolocation_models; do
  if docker volume inspect $vol >/dev/null 2>&1; then
    size=$(docker run --rm -v $vol:/check alpine du -sh /check 2>/dev/null | cut -f1)
    echo "  $vol: $size"
  fi
done

REMOTE

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ MODELS SUCCESSFULLY DEPLOYED TO VM!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "🔍 Verify volumes:"
echo "  ssh ${VM_HOST} 'docker volume ls | grep models'"
echo ""
echo "🚀 Ready to deploy application!"