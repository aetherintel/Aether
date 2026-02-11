# models/image/Dockerfile
# Self-contained Image Model Container
# Downloads EasyOCR models during build

FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies for OpenCV (EasyOCR)
# We need these to run the easyocr library to trigger the download
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN pip install --no-cache-dir easyocr opencv-python-headless

# Copy download script
COPY image/download_models.py .

# Run download
# EasyOCR -> ./easyocr_cache
RUN python download_models.py

FROM alpine:latest

WORKDIR /models

# Copy EasyOCR models
COPY --from=builder /build/easyocr_cache /models/image

CMD ["tail", "-f", "/dev/null"]