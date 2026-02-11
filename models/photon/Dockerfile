# models/photon/Dockerfile
FROM debian:bullseye-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y curl bzip2

# Reuse the script or inline it. The script has some interactive checks we don't want.
# Let's inline the download logic for reproducibility and non-interactivity.

ARG DOWNLOAD_URL="https://download1.graphhopper.com/public/extracts/by-country-code/de/photon-db-de-latest.tar.bz2"
ARG DATA_DIR="/app/photon_data"

RUN mkdir -p ${DATA_DIR}
WORKDIR ${DATA_DIR}

RUN echo "⬇️  Downloading Germany geocoding data..." && \
    curl -L "${DOWNLOAD_URL}" -o photon-de.tar.bz2 && \
    echo "📦 Extracting..." && \
    tar -xjf photon-de.tar.bz2 && \
    rm photon-de.tar.bz2

# Expect extraction to result in a 'photon_data' folder?
# The script says: rm -rf "$PHOTON_DATA_DIR/photon_data"
# And then tar -xjf. The tarball usually contains the 'photon_data' directory.
# Let's verify by listing after extraction
RUN ls -la

FROM alpine:latest
# We want the content *inside* the 'photon_data' folder to be available.
# Or the folder itself?
# The photon service expects: - ./models/geocoding/photon/photon_data:/photon/photon_data
# So it expects the *content* of the 'photon_data' directory to be mounted to /photon/photon_data
# OR it expects the directory 'photon_data' to be mounted/present.
# Let's look at the mapping: host path `.../photon_data` -> container path `/photon/photon_data`.
# If the tarball contains a directory `photon_data`, then inside /app/photon_data (builder) we have /app/photon_data/photon_data.
# We should copy /app/photon_data/photon_data to /photon_data in the final image.

COPY --from=builder /app/photon_data/photon_data /photon/photon_data
CMD ["tail", "-f", "/dev/null"]
