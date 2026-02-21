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

# Check for flags
SETUP_MODE=false
CHECK_MODE=false
DAEMON_MODE=false
WAIT_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --setup)
            SETUP_MODE=true
            shift
            ;;
        --check)
            CHECK_MODE=true
            shift
            ;;
        --daemon)
            DAEMON_MODE=true
            shift
            ;;
        --wait)
            WAIT_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --setup    Run GPU setup script on remote machine"
            echo "  --check    Verify GPU is working on remote machine"
            echo "  --daemon   Run in background (non-blocking, for pipelines)"
            echo "  --wait     Wait for GPU workers to be ready (poll until ready)"
            echo "  --help     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --setup       # Setup GPU (first time or after instance recreate)"
            echo "  $0 --check      # Verify GPU works"
            echo "  $0 --daemon     # Start GPU workers in background (non-blocking)"
            echo "  $0 --wait       # Wait for GPU workers to become ready"
            echo "  $0              # Connect to existing GPU instance"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage"
            exit 1
            ;;
    esac
done

# Handle --check mode
if [[ "$CHECK_MODE" == true ]]; then
    echo "🔍 Checking GPU on remote machine..."
    ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$REMOTE_USER@$VAST_IP" \
        "nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader && \
         docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi --query-gpu=name --format=csv,noheader"
    exit $?
fi

# Handle --wait mode (poll until GPU workers are ready)
if [[ "$WAIT_MODE" == true ]]; then
    echo "⏳ Waiting for GPU workers to be ready..."
    MAX_ATTEMPTS=120
    ATTEMPT=0
    while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
        if ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$REMOTE_USER@$VAST_IP" \
            "docker ps --format '{{.Names}}' | grep -E 'translation-worker|llm-service' | wc -l" 2>/dev/null | grep -q "2\|3\|4\|5\|6"; then
            echo "✅ GPU workers are ready!"
            exit 0
        fi
        ATTEMPT=$((ATTEMPT + 1))
        echo "   Waiting... ($ATTEMPT/$MAX_ATTEMPTS)"
        sleep 15
    done
    echo "❌ Timeout waiting for GPU workers"
    exit 1
fi

# Handle --daemon mode (run in background)
if [[ "$DAEMON_MODE" == true ]]; then
    echo "🚀 Starting GPU workers in daemon mode..."
    
    # Check if already running
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "⚠️  Tunnel already running (PID: $(cat "$PID_FILE"))"
    else
        # Kill any existing
        pkill -f "autossh.*$VAST_IP" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
    
    # Run the main connection in background
    nohup "$0" > /tmp/aether-gpu-daemon.log 2>&1 &
    BG_PID=$!
    echo $BG_PID > /tmp/aether-gpu-daemon.pid
    
    echo "✅ GPU workers started in background (PID: $BG_PID)"
    echo "   Log: /tmp/aether-gpu-daemon.log"
    echo "   Wait for ready: $0 --wait"
    exit 0
fi

# Handle --setup mode
if [[ "$SETUP_MODE" == true ]]; then
    echo "🔧 Running remote setup script..."
    ssh-keygen -R "[$VAST_IP]:$VAST_PORT" 2>/dev/null || true
    ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$REMOTE_USER@$VAST_IP" "mkdir -p $REMOTE_DIR"
    scp -P "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$SCRIPT_DIR/setup_remote_gpu.sh" "$REMOTE_USER@$VAST_IP:$REMOTE_DIR/setup_remote_gpu.sh"
    ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$REMOTE_USER@$VAST_IP" "chmod +x $REMOTE_DIR/setup_remote_gpu.sh && $REMOTE_DIR/setup_remote_gpu.sh"
    
    SETUP_RESULT=$?
    if [[ $SETUP_RESULT -eq 0 ]]; then
        echo ""
        echo "✅ Setup complete! Run '$0' to connect."
    else
        echo ""
        echo "❌ Setup failed. Check output above for details."
    fi
    exit $SETUP_RESULT
fi

# Check if GPU is already set up before connecting
echo "🔍 Checking if GPU is already set up..."
GPU_CHECK=$(ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$REMOTE_USER@$VAST_IP" "docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi --query-gpu=name --format=csv,noheader 2>&1" || echo "FAILED")

if [[ "$GPU_CHECK" == "FAILED" ]]; then
    echo "⚠️  GPU not available in Docker on remote machine."
    echo "    Run '$0 --setup' first to configure GPU support."
    exit 1
fi

echo "✅ GPU available: $GPU_CHECK"

echo "🔌 Connecting to Vast.ai GPU Instance ($VAST_IP:$VAST_PORT)..."

# ─────────────────────────────────────────────────────────────────
# 1. Dependency Check
# ─────────────────────────────────────────────────────────────────
if ! command -v autossh &> /dev/null; then
    echo "⚠️  autossh not found. Attempting to install..."
    if command -v brew &> /dev/null; then
        brew install autossh
    elif command -v apt-get &> /dev/null; then
        sudo apt-get install -y autossh
    elif command -v yum &> /dev/null; then
        sudo yum install -y autossh
    else
        echo "❌ Cannot install autossh automatically. Please install manually:"
        echo "    macOS:  brew install autossh"
        echo "    Linux:  apt install autossh"
        exit 1
    fi
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
# 3b. Post-tunnel: verify tunnel works from remote side
# ─────────────────────────────────────────────────────────────────
echo "🔍 Verifying SSH tunnel from remote side..."
if ! ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$REMOTE_USER@$VAST_IP" "nc -z localhost 6379" 2>/dev/null; then
    echo "❌ Tunnel test failed: remote cannot reach localhost:6379"
    echo "   This means Redis is not accessible through the tunnel."
    echo "   Make sure Redis is published on your local machine (docker-compose ports: 6379)"
    exit 1
fi
echo "✅ SSH tunnel working (remote → local Redis)"

# ─────────────────────────────────────────────────────────────────
# 4. Sync config + media to remote
# ─────────────────────────────────────────────────────────────────
echo "📂 Syncing config files..."
ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new \
    $SSH_OPTS "$REMOTE_USER@$VAST_IP" "mkdir -p $REMOTE_DIR"

echo "📄 Syncing .env.remote..."
scp -P "$VAST_PORT" $SSH_OPTS ".env.remote" "$REMOTE_USER@$VAST_IP:$REMOTE_DIR/.env.remote"

# Sync source code (no model weights — those are synced separately below)
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
    --exclude 'models/image' \
    --exclude 'models/llm' \
    --exclude 'backend' \
    --exclude 'frontend' \
    --exclude 'telegram_scraper' \
    --exclude 'workers/report_worker' \
    --exclude 'workers/geolocation_worker' \
    --exclude '*.gguf' \
    --exclude '*.bin' \
    --exclude '*.pt' \
    --exclude '*.pth' \
    --exclude '*.h5' \
    -e "ssh -p $VAST_PORT $SSH_OPTS" \
    ./ \
    "$REMOTE_USER@$VAST_IP:$REMOTE_DIR/"

# Model weights are baked into worker images (built by CI and pushed to GHCR).
# No model rsync needed — just pull the images on the remote.



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
ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$REMOTE_USER@$VAST_IP" \
    "cd $REMOTE_DIR && \
     docker compose -f docker-compose.remote.yml --env-file .env.remote build && \
     docker compose -f docker-compose.remote.yml --env-file .env.remote up -d --remove-orphans"

# ─────────────────────────────────────────────────────────────────
# 7. Verify workers are running and connected to Redis
# ─────────────────────────────────────────────────────────────────
echo "🔍 Verifying GPU workers..."
sleep 5

WORKER_STATUS=$(ssh -p "$VAST_PORT" -o StrictHostKeyChecking=accept-new $SSH_OPTS "$REMOTE_USER@$VAST_IP" \
    "docker ps --format '{{.Names}}: {{.Status}}' | grep -E 'translation-worker|emotion-worker|llm-service'")

echo "$WORKER_STATUS"

# Check if workers are running
if echo "$WORKER_STATUS" | grep -q "translation-worker"; then
    echo "✅ Translation worker is running"
else
    echo "❌ Translation worker NOT running - check logs:"
    ssh -p "$VAST_PORT" $SSH_OPTS "$REMOTE_USER@$VAST_IP" "docker logs \$(docker ps -q --filter name=translation-worker) 2>&1 | tail -20"
fi

if echo "$WORKER_STATUS" | grep -q "emotion-worker"; then
    echo "✅ Emotion worker is running"
else
    echo "❌ Emotion worker NOT running - check logs:"
    ssh -p "$VAST_PORT" $SSH_OPTS "$REMOTE_USER@$VAST_IP" "docker logs \$(docker ps -q --filter name=emotion-worker) 2>&1 | tail -20"
fi

if echo "$WORKER_STATUS" | grep -q "llm-service"; then
    echo "✅ LLM service is running"
else
    echo "❌ LLM service NOT running - check logs:"
    ssh -p "$VAST_PORT" $SSH_OPTS "$REMOTE_USER@$VAST_IP" "docker logs \$(docker ps -q --filter name=llm-service) 2>&1 | tail -20"
fi

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