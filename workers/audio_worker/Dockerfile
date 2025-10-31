FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg git build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (for better Docker caching)
COPY workers/audio_worker/requirements.txt .

# Install ARM-compatible CPU-only PyTorch first (from official index)
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

# Install the rest of your dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Reduce thread parallelism for stability
ENV OMP_NUM_THREADS=1
ENV MALLOC_ARENA_MAX=2

# Copy shared libs and worker code
COPY aether_lib /app/aether_lib
COPY workers/audio_worker/ /app/workers/audio_worker
COPY models/audio/whisper /app/models/audio/whisper

ENV PYTHONPATH=/app:$PYTHONPATH

CMD ["rq", "worker", "--url", "redis://redis:6379/3", "audio-jobs"]
