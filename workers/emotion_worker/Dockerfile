# ============================================================================
# workers/emotion_worker/Dockerfile
# Dockerfile for emotion analysis worker
# ============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if needed for torch)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY workers/emotion_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY workers/emotion_worker /app/workers/emotion_worker
COPY aether_lib /app/aether_lib

# Create models directory
RUN mkdir -p /app/models/emotion

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    MODELS_PATH=/app/models/emotion \
    PYTHONPATH=/app:/app/workers:/app/aether_lib

# Ensure package init files exist
RUN touch /app/workers/__init__.py && \
    touch /app/workers/emotion_worker/__init__.py

# Run RQ worker listening to emotion-jobs queue
CMD ["rq", "worker", "emotion-jobs", \
     "--with-scheduler", \
     "-u", "redis://redis:6379/4", \
     "--worker-ttl", "420", \
     "--job-monitoring-interval", "30"]