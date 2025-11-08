FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PaddlePaddle and OCR
RUN apt-get update && apt-get install -y \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY workers/image_worker/requirements.txt .
COPY aether_lib /app/aether_lib
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/models/image/easyocr

# Copy worker code
COPY workers/image_worker/ ./workers/image_worker/
RUN touch /app/workers/__init__.py && \
    touch /app/workers/image_worker/__init__.py
