FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY workers/translation_worker/requirements.txt .

RUN pip install --no-cache-dir \
    torch==2.2.2 \
    numpy==1.26.3 \
    --index-url https://download.pytorch.org/whl/cpu
    
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker file
COPY workers/translation_worker ./workers/translation_worker
COPY aether_lib /app/aether_lib

# ✅ Create models directory
RUN mkdir -p /app/models

# ✅ Environment variables
ENV PYTHONUNBUFFERED=1 \
    MODELS_PATH=/app/models \
    PYTHONPATH=/app:/app/workers:/app/aether_lib


# ensure package init files exist
RUN touch /app/workers/__init__.py && \
    touch /app/workers/translation_worker/__init__.py

