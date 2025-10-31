#!/bin/bash
# scripts/setup_photon_germany.sh

set -e  # Exit on error

echo "🗺️  Photon Geocoding Setup - Germany Edition"
echo "=============================================="
echo ""

# Configuration
PHOTON_DATA_DIR="./geocoding/photon"
DOWNLOAD_URL="https://download1.graphhopper.com/public/extracts/by-country-code/de/photon-db-de-latest.tar.bz2"
TEMP_FILE="photon-de.tar.bz2"

# Create directory
echo "📁 Creating data directory..."
mkdir -p "$PHOTON_DATA_DIR"

# Check if data already exists
if [ -d "$PHOTON_DATA_DIR/photon_data" ]; then
    echo "⚠️  Photon data already exists in $PHOTON_DATA_DIR"
    read -p "Do you want to re-download? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "✅ Using existing data"
        exit 0
    fi
    echo "🗑️  Removing old data..."
    rm -rf "$PHOTON_DATA_DIR/photon_data"
fi

# Download
echo "⬇️  Downloading Germany geocoding data (~1.5GB)..."
echo "This may take a while depending on your connection..."
cd "$PHOTON_DATA_DIR"

if command -v wget &> /dev/null; then
    wget --progress=bar:force:noscroll "$DOWNLOAD_URL" -O "$TEMP_FILE"
elif command -v curl &> /dev/null; then
    curl -# -L "$DOWNLOAD_URL" -o "$TEMP_FILE"
else
    echo "❌ Error: Neither wget nor curl found. Please install one of them."
    exit 1
fi

# Extract
echo ""
echo "📦 Extracting data..."
tar -xjf "$TEMP_FILE"

# Cleanup
echo "🧹 Cleaning up..."
rm "$TEMP_FILE"

# Get back to project root
cd - > /dev/null

# Verify
if [ -d "$PHOTON_DATA_DIR/photon_data" ]; then
    SIZE=$(du -sh "$PHOTON_DATA_DIR/photon_data" | cut -f1)
    echo ""
    echo "✅ Success! Photon Germany data installed"
    echo "   Location: $PHOTON_DATA_DIR/photon_data"
    echo "   Size: $SIZE"
    echo ""
    echo "🚀 You can now start the services with: docker compose up"
else
    echo "❌ Error: Data extraction failed"
    exit 1
fi