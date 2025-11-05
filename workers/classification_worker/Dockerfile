FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY workers/classification_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker module files directly to /app (flat structure)
COPY workers/classification_worker/*.py ./workers/classification_worker/

# Copy shared library
COPY aether_lib/ /app/aether_lib/

RUN mkdir -p /app/models/classifier
RUN touch /app/workers/__init__.py && \
    touch /app/workers/classification_worker/__init__.py
# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run worker
CMD ["rq", "worker", "--url", "redis://redis:6379/5", "classification-jobs"]