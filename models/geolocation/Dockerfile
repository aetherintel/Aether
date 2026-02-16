# models/geolocation/Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y curl unzip


# Download GeoNames (Base)
COPY geolocation_download.sh .
RUN chmod +x geolocation_download.sh && \
    mkdir -p models/geolocation/geonames && \
    ./geolocation_download.sh

# Build GeoNames Index
COPY build_geonames_index.py .
RUN python build_geonames_index.py

# Download GLiNER Model
RUN pip install gliner torch
COPY download_gliner.py .
# Ensure output directory exists for script
RUN mkdir -p models/geolocation 
# Run script to download model to models/geolocation/gliner_model
RUN python download_gliner.py

FROM alpine:latest
# Script downloads to ./models/geolocation/geonames inside the builder
COPY --from=builder /app/models/geolocation/geonames /models/geonames
COPY --from=builder /app/models/geolocation/gliner_model /models/gliner_model

CMD ["tail", "-f", "/dev/null"]