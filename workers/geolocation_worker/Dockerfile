# workers/geolocation_worker/Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Heavy deps first — cached unless explicitly changed
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir gliner

COPY workers/geolocation_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aether_lib /app/aether_lib
COPY workers/geolocation_worker/ ./workers/geolocation_worker/
COPY aether_lib/ ./aether_lib/

RUN touch /app/workers/__init__.py && \
    touch /app/workers/geolocation_worker/__init__.py

# Bake GeoNames data + index into the image
RUN mkdir -p /app/models/geolocation/geonames && \
    cd /app/models/geolocation/geonames && \
    curl -s http://download.geonames.org/export/dump/DE.zip -O && \
    unzip -q DE.zip && rm DE.zip && \
    curl -s http://download.geonames.org/export/dump/alternateNamesV2.zip -O && \
    unzip -q alternateNamesV2.zip && rm alternateNamesV2.zip

RUN python - <<'EOF'
import os, pickle
DATA_DIR = "/app/models/geolocation/geonames"
geo_index = {}
with open(os.path.join(DATA_DIR, "DE.txt"), 'r', encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) < 15:
            continue
        geonameid, name = parts[0], parts[1]
        lat, lng = float(parts[4]), float(parts[5])
        population = int(parts[14]) if parts[14].isdigit() else 0
        key = name.lower()
        entry = dict(geonameid=geonameid, name=name, lat=lat, lng=lng,
                     country=parts[8], admin1=parts[10], admin2=parts[11], population=population)
        if key not in geo_index or population > geo_index[key]['population']:
            geo_index[key] = entry
id_to_key = {v['geonameid']: k for k, v in geo_index.items()}
alt_map = {}
with open(os.path.join(DATA_DIR, "alternateNamesV2.txt"), 'r', encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) < 4:
            continue
        gid, alt = parts[1], parts[3].lower()
        if gid in id_to_key and alt != id_to_key[gid]:
            alt_map[alt] = id_to_key[gid]
with open(os.path.join(DATA_DIR, "index.pkl"), 'wb') as f:
    pickle.dump({'index': geo_index, 'alternates': alt_map, 'metadata': {'source': 'geonames.org'}}, f)
print(f"GeoNames index: {len(geo_index)} locations, {len(alt_map)} alternates")
EOF

# Download GLiNER NER model
RUN python - <<'EOF'
from gliner import GLiNER
import os
out = "/app/models/geolocation/gliner_model"
os.makedirs(out, exist_ok=True)
print("Downloading urchade/gliner_medium-v2.1 ...")
GLiNER.from_pretrained("urchade/gliner_medium-v2.1").save_pretrained(out)
print(f"GLiNER model saved to {out}")
EOF

ENV PYTHONPATH=/app:/app/shared_libs \
    PYTHONUNBUFFERED=1 \
    GEONAMES_DATA_DIR=/app/models/geolocation/geonames \
    GLINER_MODEL_PATH=/app/models/geolocation/gliner_model \
    PHOTON_URL=http://photon:2322
