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
# 3. Install NVIDIA Container Toolkit
# ─────────────────────────────────────────────────────────────────
if dpkg -l | grep -q nvidia-container-toolkit; then
    echo "✅ NVIDIA Container Toolkit already installed"
else
    echo "📦 Installing NVIDIA Container Toolkit..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null

    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
        | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

    apt-get update -qq
    apt-get install -y nvidia-container-toolkit
fi

# ─────────────────────────────────────────────────────────────────
# 4. Configure Docker runtime
# ─────────────────────────────────────────────────────────────────
echo "⚙️  Configuring Docker NVIDIA runtime..."
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# ─────────────────────────────────────────────────────────────────
# 5. Verify everything works
# ─────────────────────────────────────────────────────────────────
echo "🧪 Verification..."
echo "   nvidia-smi:"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
echo ""
echo "   Docker GPU test:"
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null \
    && echo "✅ Docker GPU passthrough works!" \
    || echo "⚠️  Docker GPU test failed — containers may not see GPU"

echo ""
echo "🎉 Setup complete. Ready for GPU workers."