# scripts/PHOTON_SETUP.md

# 🗺️ Photon Geocoding Setup

Aether uses [Photon](https://photon.komoot.io/) for offline geocoding of locations mentioned in Telegram messages.

## Quick Start (Germany)

### Option 1: Bash Script (Linux/Mac)
```bash
chmod +x scripts/setup_photon_germany.sh
./scripts/setup_photon_germany.sh
```

### Option 2: Python Script (All platforms)
```bash
pip install requests  # If not already installed
python scripts/setup_photon_germany.py
```

## What This Does

1. Downloads pre-indexed Germany OSM data (~1.5 GB)
2. Extracts to `./models/geocoding/photon/photon_data/`
3. Ready for use with Docker Compose

## Other Countries/Regions

If you need geocoding for other regions, download from:
https://download1.graphhopper.com/public/extracts/

### Available Extracts:
- **By Country**: `by-country-code/de/` (Germany), `by-country-code/fr/` (France), etc.
- **By Continent**: `europe/`, `north-america/`, etc.
- **Full Planet**: `photon-db-latest.tar.bz2` (~70 GB)

### Example: Download France instead
```bash
# Edit the script and change the URL to:
DOWNLOAD_URL="https://download1.graphhopper.com/public/extracts/by-country-code/fr/photon-db-fr-latest.tar.bz2"
```

## Manual Download

If the scripts don't work, download manually:
```bash
mkdir -p ./models/geocoding/photon
cd ./models/geocoding/photon

# Download
wget https://download1.graphhopper.com/public/extracts/by-country-code/de/photon-db-de-latest.tar.bz2

# Extract
tar -xjf photon-db-de-latest.tar.bz2

# Cleanup
rm photon-db-de-latest.tar.bz2
```

## Troubleshooting

### "No such file or directory"
Make sure you run the script from the project root directory.

### "Connection timeout"
The download is large (~1.5GB). Use a stable internet connection.

### "Permission denied"
```bash
sudo chown -R $USER:$USER ./models/geocoding/photon
```

## Storage Requirements

| Region          | Size     |
|-----------------|----------|
| Germany         | ~1.5 GB  |
| France          | ~2.5 GB  |
| Europe          | ~15 GB   |
| Full Planet     | ~70 GB   |

## Verification

After setup, check that the data exists:
```bash
ls -lh ./models/geocoding/photon/photon_data/
```

You should see Elasticsearch index files.


To Predownload libpostal into Geolocation dir:

```bash
# Create the directory from project root
mkdir -p ./models/geolocation

# Download using Docker temporarily 
docker run --rm \
  -v $(pwd)/models/geolocation:/data \
  python:3.11-slim \
  bash -c "
    apt-get update && apt-get install -y curl git build-essential autoconf automake libtool pkg-config && \
    git clone https://github.com/openvenues/libpostal /tmp/libpostal && \
    cd /tmp/libpostal && \
    ./bootstrap.sh && \
    ./configure --datadir=/data && \
    make -j4 && make install && ldconfig && \
    libpostal_data download all /data
  "
```