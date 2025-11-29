FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg git build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY aether_lib /app/aether_lib
# Copy requirements first (for better Docker caching)
COPY workers/audio_worker/requirements.txt .

# Install the rest of your dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Reduce thread parallelism for stability
ENV OMP_NUM_THREADS=1
ENV MALLOC_ARENA_MAX=2

# Copy shared libs and worker code
COPY aether_lib /app/aether_lib
COPY workers/audio_worker/ /app/workers/audio_worker

RUN mkdir -p /app/models/audio/whisper
RUN touch /app/workers/__init__.py && \
    touch /app/workers/audio_worker/__init__.py

ENV PYTHONPATH=/app:/app/shared_libs:$PYTHONPATH
