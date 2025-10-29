# scripts/setup_geonames.sh
#!/bin/bash

set -e

echo "📍 GeoNames Setup for Germany"
echo "=============================="

DATA_DIR="./models/geolocation/geonames"
mkdir -p "$DATA_DIR"

cd "$DATA_DIR"

# Download German cities (> 1000 population)
echo "⬇️  Downloading German cities..."
curl  http://download.geonames.org/export/dump/DE.zip -O -s
unzip -q DE.zip
rm DE.zip

# Download alternate names (for "Alex" -> "Alexanderplatz" mapping)
echo "⬇️  Downloading alternate names..."
curl  http://download.geonames.org/export/dump/alternateNamesV2.zip -O -s
unzip -q alternateNamesV2.zip
rm alternateNamesV2.zip

echo "✅ GeoNames data downloaded"
echo "   Size: $(du -sh . | cut -f1)"