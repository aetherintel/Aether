# ============================================================================
# workers/classification_worker/Dockerfile
# ============================================================================
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY workers/classification_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY workers/classification_worker/ /app/workers/classification_worker/

# Copy shared library
COPY aether_lib/ /app/aether_lib/

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/aether_lib

RUN touch /app/workers/__init__.py && \
    touch /app/workers/classification_worker/__init__.py

# Run worker
CMD ["rq", "worker", "--url", "redis://redis:6379/5", "classification-jobs"]