# workers/geolocation_worker/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install minimal system dependencies (nur für spaCy)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY workers/geolocation_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY workers/geolocation_worker/ ./workers/geolocation_worker/
COPY aether_lib/ ./aether_lib/

RUN mkdir -p /app/models/geolocation/geonames

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV GEONAMES_DATA_DIR=/app/models/geolocation/geonames
ENV PHOTON_URL=http://photon:2322

CMD ["rq", "worker", "--url", "redis://redis:6379/6", "geolocation-jobs"]