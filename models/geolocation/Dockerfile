# models/geolocation/Dockerfile
FROM debian:bullseye-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y curl unzip

COPY geolocation_download.sh .
RUN chmod +x geolocation_download.sh && \
    mkdir -p models/geolocation/geonames && \
    ./geolocation_download.sh

FROM alpine:latest
# Script downloads to ./models/geolocation/geonames inside the builder
COPY --from=builder /app/models/geolocation/geonames /models/geonames
CMD ["tail", "-f", "/dev/null"]