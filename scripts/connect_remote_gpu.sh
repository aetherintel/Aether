#!/bin/bash
set -e

# =============================================================================
# scripts/connect_remote_gpu.sh
# =============================================================================
# Connects local Aether stack to vast.ai GPU instance.
# Must be run from project root (where docker-compose.remote.yml lives).
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

PID_FILE="/tmp/aether-gpu-tunnel.pid"

# Load connection config (VAST_IP, VAST_PORT)
if [[ -f .env.remote.connection ]]; then
    source .env.remote.connection
fi

VAST_IP="${VAST_IP:?❌ Set VAST_IP in .env.remote.connection}"
VAST_PORT="${VAST_PORT:?❌ Set VAST_PORT in .env.remote.connection}"
# Optional: SSH_KEY_PATH
if [[ -n "$SSH_KEY_PATH" ]]; then
    # Trim whitespace
    SSH_KEY_PATH="$(echo -e "${SSH_KEY_PATH}" | tr -d '[:space:]')"
    
    echo "🔑 Using Key: '$SSH_KEY_PATH'"
    if [[ ! -f "$SSH_KEY_PATH" ]]; then
        echo "❌ SSH key file not found at: '$SSH_KEY_PATH'"
        ls -l "$SSH_KEY_PATH" 2>/dev/null || echo "   (ls failed)"
        exit 1
    fi
    SSH_OPTS="-i $SSH_KEY_PATH"
else
    SSH_OPTS=""
fi

REMOTE_USER="root"
REMOTE_DIR="~/aether"

# Check for --setup flag
if [[ "$1" == "--setup" ]]; then
    echo "🔧 Running remote setup script..."
    scp -P "$VAST_PORT" $SSH_OPTS "$SCRIPT_DIR/setup_remote_gpu.sh" "$REMOTE_USER@$VAST_IP:$REMOTE_DIR/setup_remote_gpu.sh"
    ssh -p "$VAST_PORT" $SSH_OPTS "$REMOTE_USER@$VAST_IP" "chmod +x $REMOTE_DIR/setup_remote_gpu.sh && $REMOTE_DIR/setup_remote_gpu.sh"
    exit 0
fi

echo "🔌 Connecting to Vast.ai GPU Instance ($VAST_IP:$VAST_PORT)..."

# ─────────────────────────────────────────────────────────────────
# 1. Dependency Check
# ─────────────────────────────────────────────────────────────────
if ! command -v autossh &> /dev/null; then
    echo "⚠️  autossh not found. Install it:"
    echo "    macOS:  brew install autossh"
    echo "    Linux:  apt install autossh"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────
# 2. Kill existing tunnel (prevent duplicates)
# ─────────────────────────────────────────────────────────────────
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "🔄 Stopping existing tunnel (PID: $(cat "$PID_FILE"))..."
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
    sleep 1
fi

# ─────────────────────────────────────────────────────────────────
# 3. Pre-flight: verify local services
# ─────────────────────────────────────────────────────────────────
echo "🔍 Checking local services..."
for port in 6379 5432 7687; do
    if ! nc -z localhost "$port" 2>/dev/null; then
        echo "❌ Local port $port not reachable. Is docker compose up?"
        exit 1
    fi
done
echo "✅ Local services reachable"

# ─────────────────────────────────────────────────────────────────
# 4. Sync config + media to remote
# ─────────────────────────────────────────────────────────────────
echo "📂 Syncing config files..."
ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new \
    $SSH_OPTS "$REMOTE_USER@$VAST_IP" "mkdir -p $REMOTE_DIR"

echo "📄 Syncing .env.remote..."
scp -P "$VAST_PORT" $SSH_OPTS ".env.remote" "$REMOTE_USER@$VAST_IP:$REMOTE_DIR/.env.remote"

# We explicitly exclude heavy/unneeded items.
# We do NOT use .dockerignore because it excludes 'models/', which we need for Dockerfiles.
echo "📂 Syncing project source code (for remote build)..."
rsync -avzP \
    --exclude '.git' \
    --exclude '.github' \
    --exclude 'venv' \
    --exclude 'node_modules' \
    --exclude 'shared/media' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude 'models/geocoding' \
    --exclude 'models/classifier' \
    --exclude 'models/photon' \
    --exclude 'models/audio' \
    --exclude 'models/audio' \
    --exclude 'models/image' \
    --exclude 'backend' \
    --exclude 'frontend' \
    --exclude 'telegram_scraper' \
    --exclude 'workers/report_worker' \
    --exclude 'workers/geolocation_worker' \
    --exclude '*.gguf' \
    --exclude '*.bin' \
    --exclude '*.safetensors' \
    --exclude '*.pt' \
    --exclude '*.pth' \
    --exclude '*.h5' \
    -e "ssh -p $VAST_PORT $SSH_OPTS" \
    ./ \
    "$REMOTE_USER@$VAST_IP:$REMOTE_DIR/"



# ─────────────────────────────────────────────────────────────────
# 5. Establish SSH reverse tunnel
# ─────────────────────────────────────────────────────────────────
echo "🚇 Establishing reverse SSH tunnel..."
echo "   Redis    localhost:6379 → remote:6379"
echo "   Postgres localhost:5432 → remote:5432"
echo "   Neo4j    localhost:7687 → remote:7687"
echo "   LLM API  localhost:8001 → remote:8001 (HTTP)"

autossh -M 0 -f -N \
    -o "ServerAliveInterval=15" \
    -o "ServerAliveCountMax=3" \
    -o "ExitOnForwardFailure=yes" \
    -o "StrictHostKeyChecking=accept-new" \
    $SSH_OPTS \
    -L 8001:localhost:8001 \
    -R 6379:localhost:6379 \
    -R 5432:localhost:5432 \
    -R 7687:localhost:7687 \
    -p "$VAST_PORT" "$REMOTE_USER@$VAST_IP"

# Capture PID (autossh -f forks, grab the child)
sleep 1
pgrep -f "autossh.*$VAST_IP.*$VAST_PORT" | head -1 > "$PID_FILE"
echo "✅ Tunnel established (PID: $(cat "$PID_FILE"))"

# ─────────────────────────────────────────────────────────────────
# 6. Launch remote workers
# ─────────────────────────────────────────────────────────────────
echo "🚀 Building and Launching remote GPU workers..."
ssh -p "$VAST_PORT" $SSH_OPTS "$REMOTE_USER@$VAST_IP" \
    "cd $REMOTE_DIR && \
     docker compose -f docker-compose.remote.yml --env-file .env.remote build && \
     docker compose -f docker-compose.remote.yml --env-file .env.remote up -d --remove-orphans"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  🎉 Hybrid Setup Active"
echo "═══════════════════════════════════════════════════"
echo "  Local App:   docker compose (your Mac)"
echo "  GPU Workers: vast.ai ($VAST_IP)"
echo "  Tunnel PID:  $(cat "$PID_FILE")"
echo ""
echo "  Commands:"
echo "    Logs:    ssh -p $VAST_PORT $SSH_OPTS $REMOTE_USER@$VAST_IP 'cd $REMOTE_DIR && docker compose -f docker-compose.remote.yml logs -f'"
echo "    Stop:    kill \$(cat $PID_FILE) && ssh -p $VAST_PORT $SSH_OPTS $REMOTE_USER@$VAST_IP 'cd $REMOTE_DIR && docker compose -f docker-compose.remote.yml down'"
echo "    Re-Sync & Build: ./scripts/connect_remote_gpu.sh"
echo "═══════════════════════════════════════════════════"