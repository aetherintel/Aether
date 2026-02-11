#!/bin/bash
# deploy_vm.sh

set -e

echo "🚀 Deploying Aether to VM"

# 1. Update Code (Assuming this script is run on VM or triggered via CI/CD, 
# or we just need to instruct user to run docker commands)
# If this is run from local machine to trigger VM update:

VM_HOST="${VM_HOST:-user@your-vm-ip}"
VM_DIR="~/app"

echo "Using VM: $VM_HOST"

# 2. Copy configuration and models
echo "📂 Copying configuration..."
scp docker-compose.prod.yml $VM_HOST:$VM_DIR/docker-compose.yml
scp .env.prod $VM_HOST:$VM_DIR/.env 2>/dev/null || echo "⚠️  No .env.prod found, make sure .env exists on VM"

echo "📂 Syncing LLM models..."
# Sync the models directory (creating if needed)
ssh $VM_HOST "mkdir -p $VM_DIR/models/llm"
rsync -avz --progress ./models/llm/ $VM_HOST:$VM_DIR/models/llm/

# 3. Trigger Docker Pull & Update
echo "🐳 Updating containers..."
ssh $VM_HOST << 'EOF'
  cd ~/app
  
  echo "⬇️  Pulling latest images..."
  docker compose pull

  echo "🔄 Restarting services..."
  # We might need to remove volumes to force model updates if they changed?
  # WARNING: This deletes data using the volume!
  # Use with caution. For models, it might be safer to let the user decide.
  # But technically, if the model image changes, the data inside the *image* changes.
  # But the VOLUME persists.
  # To update the volume content from the image, the volume needs to be empty or re-created.
  
  # STRATEGY: We don't auto-delete volumes here to be safe.
  # But we warn the user.
  
  docker compose up -d --remove-orphans

  echo "✅ Deployment complete!"
EOF
