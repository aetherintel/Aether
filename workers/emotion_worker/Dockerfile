# ============================================================================
# workers/emotion_worker/Dockerfile
# Dockerfile for emotion analysis worker
# ============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if needed for torch)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
COPY aether_lib /app/aether_lib
# Copy requirements and install
COPY workers/emotion_worker/requirements.txt .
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker module files directly to /app (flat structure)
COPY workers/emotion_worker/*.py ./workers/emotion_worker/

COPY aether_lib /app/aether_lib

# Create models directory
RUN mkdir -p /app/models/emotion
RUN touch /app/workers/__init__.py && \
    touch /app/workers/emotion_worker/__init__.py

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    MODELS_PATH=/app/models/emotion \
    PYTHONPATH=/app:/app/workers:/app/aether_lib
