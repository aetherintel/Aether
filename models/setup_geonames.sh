#!/bin/bash
# scripts/setup_geolocation_complete.sh

set -e

echo "🗺️  Complete Geolocation Setup"
echo "================================"
echo ""

# Configuration
GEO_DIR="./geolocation"
GEONAMES_DIR="$GEO_DIR/geonames"
PHOTON_DIR="$GEO_DIR/photon"

# Clean start?
if [ -d "$GEO_DIR" ]; then
    echo "⚠️  Existing geolocation data found"
    read -p "Delete and start fresh? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing old data..."
        rm -rf "$GEO_DIR"
    fi
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p "$GEONAMES_DIR"
mkdir -p "$PHOTON_DIR"

# ============================================================================
# PART 1: GeoNames Setup
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 Part 1/2: GeoNames Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$GEONAMES_DIR"

# Download German cities
if [ ! -f "DE.txt" ]; then
    echo "⬇️  Downloading German cities database..."
    curl -# -L -o DE.zip http://download.geonames.org/export/dump/DE.zip
    echo "📦 Extracting..."
    unzip -q DE.zip
    rm DE.zip
    ENTRIES=$(wc -l < DE.txt)
    echo "✅ DE.txt: $ENTRIES entries"
else
    echo "✅ DE.txt already exists"
fi

# Download and filter alternate names
if [ ! -f "alternateNamesDE.txt" ]; then
    echo ""
    echo "⬇️  Downloading alternate names (this is large, ~2GB)..."
    curl -# -L -o alternateNamesV2.zip http://download.geonames.org/export/dump/alternateNamesV2.zip

    echo "📦 Extracting..."
    unzip -q alternateNamesV2.zip

    echo "🔍 Filtering for German locations only..."
    echo "   (Reducing from 30M+ to ~500k entries)"

    # Extract all German geonameids
    cut -f1 DE.txt > german_ids.tmp

    # Filter alternates to only German locations
    awk 'NR==FNR{ids[$1]=1; next} $2 in ids' german_ids.tmp alternateNamesV2.txt > alternateNamesDE.txt

    # Cleanup
    rm alternateNamesV2.txt german_ids.tmp alternateNamesV2.zip

    ALT_ENTRIES=$(wc -l < alternateNamesDE.txt)
    echo "✅ alternateNamesDE.txt: $ALT_ENTRIES entries"
else
    echo "✅ alternateNamesDE.txt already exists"
fi

# Build pickle index
echo ""
echo "🔧 Building optimized Python index (pickle)..."

python3 << 'PYTHON_SCRIPT'
import pickle
import sys
import time

print("   Reading DE.txt...")
start_time = time.time()

GEONAMES_INDEX = {}
ALTERNATE_NAMES = {}

# Load main German locations
with open('DE.txt', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if i % 50000 == 0:
            print(f"   Processed {i:,} entries...", end='\r')
        
        parts = line.strip().split('\t')
        if len(parts) < 19:
            continue
        
        geonameid = parts[0]
        name = parts[1]
        
        try:
            lat = float(parts[4])
            lng = float(parts[5])
        except ValueError:
            continue
        
        feature_class = parts[6]
        feature_code = parts[7]
        country = parts[8]
        admin1 = parts[10]  # State
        admin2 = parts[11]  # County
        population = int(parts[14]) if parts[14].isdigit() else 0
        
        # Only index relevant features
        if feature_class in ['P', 'A', 'S', 'L', 'T']:
            key = name.lower()
            GEONAMES_INDEX[key] = {
                'geonameid': geonameid,
                'name': name,
                'lat': lat,
                'lng': lng,
                'feature_class': feature_class,
                'feature_code': feature_code,
                'country': country,
                'admin1': admin1,
                'admin2': admin2,
                'population': population
            }

print(f"\n   ✓ Loaded {len(GEONAMES_INDEX):,} locations")

# Load alternate names
print("   Reading alternateNamesDE.txt...")
id_to_name = {v['geonameid']: k for k, v in GEONAMES_INDEX.items()}

with open('alternateNamesDE.txt', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if i % 50000 == 0:
            print(f"   Processed {i:,} alternates...", end='\r')
        
        parts = line.strip().split('\t')
        if len(parts) < 4:
            continue
        
        geonameid = parts[1]
        iso_lang = parts[2] if len(parts) > 2 else ''
        alt_name = parts[3].lower()
        
        # Only German and generic names
        if iso_lang not in ['de', '', 'link', 'abbr', 'short']:
            continue
        
        # Skip very long names (likely not useful)
        if len(alt_name) > 100:
            continue
        
        # Map to canonical name
        if geonameid in id_to_name:
            ALTERNATE_NAMES[alt_name] = id_to_name[geonameid]

print(f"\n   ✓ Loaded {len(ALTERNATE_NAMES):,} alternate names")

# Save as pickle
print("   Writing index.pkl...")
with open('index.pkl', 'wb') as f:
    pickle.dump({
        'index': GEONAMES_INDEX,
        'alternates': ALTERNATE_NAMES,
        'metadata': {
            'created': time.time(),
            'locations': len(GEONAMES_INDEX),
            'alternates': len(ALTERNATE_NAMES)
        }
    }, f, protocol=pickle.HIGHEST_PROTOCOL)

elapsed = time.time() - start_time
print(f"\n✅ Index built in {elapsed:.1f}s")
print(f"   Locations: {len(GEONAMES_INDEX):,}")
print(f"   Alternates: {len(ALTERNATE_NAMES):,}")

# Print some example mappings
print("\n   Example mappings:")
examples = [
    ('alex', 'Alexanderplatz'),
    ('berlin', 'Berlin'),
    ('münchen', 'München'),
]
for short, expected in examples:
    if short in ALTERNATE_NAMES:
        canonical = ALTERNATE_NAMES[short]
        actual = GEONAMES_INDEX[canonical]['name']
        print(f"      '{short}' → '{actual}'")
    elif short in GEONAMES_INDEX:
        print(f"      '{short}' → '{GEONAMES_INDEX[short]['name']}'")

PYTHON_SCRIPT

if [ $? -eq 0 ]; then
    echo ""
    echo "🧹 Cleaning up text files (keeping only pickle)..."
    # Keep only the pickle, remove large text files
    # rm DE.txt alternateNamesDE.txt  # Uncomment if you want to delete
    echo "   (Text files kept for reference)"
fi

cd - > /dev/null

# ============================================================================
# PART 2: Photon Setup
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗺️  Part 2/2: Photon Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$PHOTON_DIR"

if [ ! -d "photon_data" ]; then
    echo "⬇️  Downloading Photon Germany database (~1.5GB)..."
    curl -L -o photon-db-de-latest.tar.bz2 https://download1.graphhopper.com/public/extracts/by-country-code/de/photon-db-de-latest.tar.bz2
    
    echo "📦 Extracting..."
    tar -xjf photon-db-de-latest.tar.bz2
    
    echo "🧹 Cleaning up..."
    rm photon-db-de-latest.tar.bz2
    
    echo "✅ Photon data ready"
else
    echo "✅ Photon data already exists"
fi

cd - > /dev/null

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

GEONAMES_SIZE=$(du -sh "$GEONAMES_DIR" | cut -f1)
PHOTON_SIZE=$(du -sh "$PHOTON_DIR" | cut -f1)
TOTAL_SIZE=$(du -sh "$GEO_DIR" | cut -f1)

echo "📊 Summary:"
echo "   GeoNames: $GEONAMES_SIZE"
echo "   Photon:   $PHOTON_SIZE"
echo "   Total:    $TOTAL_SIZE"
echo ""
echo "📁 Structure:"
echo "   $GEONAMES_DIR/index.pkl        (optimized index)"
echo "   $PHOTON_DIR/photon_data/       (OSM geocoding)"
echo ""
echo "🚀 Next steps:"
echo "   docker compose --env-file .env.dev up --build"
echo ""