#!/bin/bash
set -e

# =============================================================================
# scripts/setup_remote_gpu.sh
# =============================================================================
# Installs NVIDIA Container Toolkit on a vast.ai instance.
# CRITICAL: Does NOT touch the nvidia-driver to avoid kernel/library mismatch.
# =============================================================================

echo "🔧 Setting up NVIDIA Container Toolkit..."

# ─────────────────────────────────────────────────────────────────
# 1. Detect loaded kernel driver version
# ─────────────────────────────────────────────────────────────────
if [[ -f /proc/driver/nvidia/version ]]; then
    KERNEL_VERSION=$(grep -oP 'NVRM version:.*\s+\K[0-9]+\.[0-9]+\.[0-9]+' /proc/driver/nvidia/version)
    echo "✅ Kernel driver loaded: $KERNEL_VERSION"
else
    echo "❌ No NVIDIA kernel driver found. This instance has no GPU or driver."
    exit 1
fi

# Check for mismatch BEFORE doing anything
if command -v nvidia-smi &>/dev/null; then
    if nvidia-smi &>/dev/null; then
        echo "✅ nvidia-smi works — driver is healthy"
    else
        LIB_VERSION=$(nvidia-smi 2>&1 | grep -oP 'NVML library version: \K[0-9.]+' || true)
        echo "⚠️  Driver/Library MISMATCH detected!"
        echo "   Kernel module: $KERNEL_VERSION"
        echo "   NVML library:  $LIB_VERSION"
        echo ""
        echo "   Attempting fix: downgrading userspace to match kernel..."

        # Extract major version (e.g. 580.95.05 → 580)
        MAJOR=$(echo "$KERNEL_VERSION" | cut -d. -f1)

        # Hold any nvidia driver packages to prevent future upgrades
        apt-mark hold nvidia-driver-* libnvidia-* 2>/dev/null || true

        # Try to install the exact matching userspace version
        apt-get update -qq
        if apt-get install -y --allow-downgrades \
            "libnvidia-compute-${MAJOR}-server=${KERNEL_VERSION}-*" \
            "libnvidia-ml-dev=${KERNEL_VERSION}-*" 2>/dev/null; then
            echo "✅ Downgraded userspace libs to $KERNEL_VERSION"
        else
            echo "⚠️  Could not find exact matching packages."
            echo "   Trying reboot instead..."
            echo "   (If reboot fails, destroy this instance and rent a new one)"
            sudo reboot || echo "❌ Reboot not permitted. Please destroy and recreate the instance."
            exit 1
        fi

        # Verify fix
        if nvidia-smi &>/dev/null; then
            echo "✅ nvidia-smi works after fix!"
        else
            echo "❌ Still broken. Reboot or recreate instance."
            sudo reboot || exit 1
        fi
    fi
fi

# ─────────────────────────────────────────────────────────────────
# 2. Pin nvidia packages to prevent auto-upgrade mismatch
# ─────────────────────────────────────────────────────────────────
echo "📌 Pinning NVIDIA driver packages to prevent auto-upgrade..."
apt-mark hold $(dpkg -l | grep -oP 'nvidia-driver-\S+' | head -5) 2>/dev/null || true
apt-mark hold $(dpkg -l | grep -oP 'libnvidia-\S+' | head -10) 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────
# 3. Fix APT sources and Install NVIDIA Container Toolkit
# ─────────────────────────────────────────────────────────────────
echo "📦 Installing NVIDIA Container Toolkit..."

# Check if already installed
if dpkg -l | grep -q nvidia-container-toolkit; then
    echo "✅ NVIDIA Container Toolkit already installed"
else
    echo "🔧 Fixing APT sources..."
    
    # Fix broken apt sources - use archive.ubuntu.com instead of security
    cat > /etc/apt/sources.list << 'EOF'
deb http://archive.ubuntu.com/ubuntu jammy main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu jammy-security main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu jammy-backports main restricted universe multiverse
EOF
    
    # Try to install without updating first (sources might be cached)
    apt-get install -y --allow-unauthenticated curl gnupg2 ca-certificates lsb-release 2>/dev/null || true
    
    # Add NVIDIA repository
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null || true
    
    echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/\$(ARCH) /" \
        | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

    apt-get update --allow-insecure-repositories -qq 2>/dev/null || true
    apt-get install -y --allow-unauthenticated nvidia-container-toolkit 2>/dev/null || {
        echo "⚠️ apt install failed, trying manual installation..."
    }
fi

# Manual install of nvidia-container-runtime if not found
if ! command -v nvidia-container-runtime &>/dev/null; then
    echo "📦 Manually installing nvidia-container-runtime..."
    
    # Download and install nvidia-container-runtime
    cd /tmp
    curl -fsSL https://github.com/NVIDIA/nvidia-container-runtime/releases/download/v1.16.1/nvidia-container-runtime_1.16.1_amd64.tar.gz -o nvidia-container-runtime.tar.gz || true
    
    if [ -f nvidia-container-runtime.tar.gz ]; then
        tar -xzf nvidia-container-runtime.tar.gz
        cp nvidia-container-runtime/nvidia-container-runtime /usr/bin/ || true
        chmod +x /usr/bin/nvidia-container-runtime
        rm -rf nvidia-container-runtime*
        echo "✅ nvidia-container-runtime installed manually"
    else
        echo "⚠️ Could not download nvidia-container-runtime"
    fi
fi

# ─────────────────────────────────────────────────────────────────
# 4. Configure Docker runtime properly
# ─────────────────────────────────────────────────────────────────
echo "⚙️  Configuring Docker NVIDIA runtime..."

# Try to configure nvidia-ctk (newer method)
if command -v nvidia-ctk &>/dev/null; then
    nvidia-ctk runtime configure --runtime=docker --config=base 2>/dev/null || true
fi

# Manual daemon.json config - try nvidia runtime, fallback to nvidia-container-runtime-cli
mkdir -p /etc/docker

# Find nvidia-container-runtime path
NVIDIA_RUNTIME_PATH=""
if command -v nvidia-container-runtime &>/dev/null; then
    NVIDIA_RUNTIME_PATH=$(which nvidia-container-runtime)
elif [ -f /usr/bin/nvidia-container-runtime ]; then
    NVIDIA_RUNTIME_PATH="/usr/bin/nvidia-container-runtime"
elif [ -f /usr/local/bin/nvidia-container-runtime ]; then
    NVIDIA_RUNTIME_PATH="/usr/local/bin/nvidia-container-runtime"
fi

if [ -n "$NVIDIA_RUNTIME_PATH" ]; then
    echo "   Using nvidia-container-runtime: $NVIDIA_RUNTIME_PATH"
    cat > /etc/docker/daemon.json << EOF
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "$NVIDIA_RUNTIME_PATH",
            "runtimeArgs": []
        }
    }
}
EOF
fi

cat /etc/docker/daemon.json
echo "   Attempting to restart Docker..."
if command -v systemctl &>/dev/null && systemctl is-active docker &>/dev/null; then
    docker stop $(docker ps -aq) 2>/dev/null || true
    systemctl daemon-reload 2>/dev/null || true
    systemctl restart docker 2>/dev/null || true
elif command -v service &>/dev/null; then
    service docker stop 2>/dev/null || true
    service docker start 2>/dev/null || true
else
    # Just try to reload config without full restart
    pkill -HUP dockerd 2>/dev/null || true
fi

# Wait for docker to be ready
sleep 3

# ─────────────────────────────────────────────────────────────────
# 5. Verify everything works
# ─────────────────────────────────────────────────────────────────
echo "🧪 Verification..."
echo "   nvidia-smi:"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

echo ""
echo "   Docker daemon.json:"
cat /etc/docker/daemon.json 2>/dev/null || echo "   (default config)"

echo ""
echo "   Docker GPU test:"
GPU_TEST=$(docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi --query-gpu=name --format=csv,noheader 2>&1) && {
    echo "✅ $GPU_TEST"
    echo "✅ Docker GPU passthrough works!"
} || {
    echo "❌ Docker GPU test failed!"
    echo "   Output: $GPU_TEST"
    echo ""
    echo "🔧 Attempting recovery..."
    
    # Try to fix by restarting containerd and docker (may fail on vast.ai)
    if command -v systemctl &>/dev/null; then
        systemctl restart containerd 2>/dev/null || true
        systemctl restart docker 2>/dev/null || true
    fi
    pkill -HUP dockerd 2>/dev/null || true
    sleep 3
    
    GPU_TEST_RETRY=$(docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi --query-gpu=name --format=csv,noheader 2>&1) && {
        echo "✅ Recovery successful! $GPU_TEST_RETRY"
    } || {
        echo "❌ Recovery failed. Manual intervention needed."
        echo "   Try: sudo reboot"
        exit 1
    }
}

echo ""
echo "🎉 Setup complete. Ready for GPU workers."