#!/usr/bin/env bash
# =============================================================================
# server-setup.sh — One-time setup for Aether production server (Fedora 43)
# Run with:
#   ssh -i ~/.ssh/id_ed25519_gh_actions_aethery fedora@<host> 'bash -s' < scripts/server-setup.sh
# =============================================================================
set -euo pipefail

echo "============================================="
echo " Aether Server Setup — Fedora 43"
echo "============================================="

# ─────────────────────────────────────────────
# 1. System update
# ─────────────────────────────────────────────
echo ""
echo "📦 Updating system packages..."
sudo dnf upgrade -y --quiet

# ─────────────────────────────────────────────
# 2. Install Docker (official Docker repo)
# ─────────────────────────────────────────────
echo ""
echo "🐳 Installing Docker..."
sudo dnf config-manager addrepo \
  --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo

sudo dnf install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

# ─────────────────────────────────────────────
# 3. Start & enable Docker
# ─────────────────────────────────────────────
echo ""
echo "🚀 Enabling Docker service..."
sudo systemctl enable --now docker

# ─────────────────────────────────────────────
# 4. Add fedora user to docker group (no sudo needed)
# ─────────────────────────────────────────────
echo ""
echo "👤 Adding fedora user to docker group..."
sudo usermod -aG docker fedora

# ─────────────────────────────────────────────
# 5. Install useful tools
# ─────────────────────────────────────────────
echo ""
echo "🔧 Installing helper tools..."
sudo dnf install -y git curl jq openssl

# ─────────────────────────────────────────────
# 6. Create app directory structure
# ─────────────────────────────────────────────
echo ""
echo "📁 Creating app directories..."
mkdir -p ~/app
mkdir -p ~/app/certbot/{www,conf}

# ─────────────────────────────────────────────
# 7. Configure firewall (open 80, 443)
# ─────────────────────────────────────────────
echo ""
echo "🔥 Configuring firewall..."
if command -v firewall-cmd &>/dev/null; then
  sudo firewall-cmd --permanent --add-service=http
  sudo firewall-cmd --permanent --add-service=https
  sudo firewall-cmd --reload
  echo "✅ Firewall updated"
else
  echo "⚠️  firewalld not found — skipping"
fi

# ─────────────────────────────────────────────
# 8. Verify
# ─────────────────────────────────────────────
echo ""
echo "✅ Verifying installation..."
sudo docker --version
sudo docker compose version

echo ""
echo "============================================="
echo " Setup complete!"
echo ""
echo " ⚠️  IMPORTANT: You must log out and back in"
echo "    (or run: newgrp docker) before the"
echo "    docker group membership takes effect."
echo "============================================="
