# models/image/Dockerfile
# Self-contained Image Model Container
# 1. Downloads EasyOCR models during build
# 2. Exposes them via volume

# Stage 1: Downloader
FROM python:3.11-slim as downloader

WORKDIR /build
COPY image/download_models.py .

# Install system dependencies for OpenCV (required by easyocr -> opencv-python-headless)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies for downloading
RUN pip install easyocr opencv-python-headless --no-cache-dir

# Run download script
# This populates /build/easyocr_cache
RUN python download_models.py

# Stage 2: Final minimal image
FROM alpine:latest

# Create directory
WORKDIR /models

# Copy downloaded models from builder to /models root
# This way the volume 'app_image_models' contains the files directly
COPY --from=downloader /build/easyocr_cache /models

CMD ["tail", "-f", "/dev/null"]