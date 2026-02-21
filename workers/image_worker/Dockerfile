FROM python:3.11-slim

# System deps for EasyOCR / OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY workers/image_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aether_lib /app/aether_lib
COPY workers/image_worker/ ./workers/image_worker/

RUN touch /app/workers/__init__.py && \
    touch /app/workers/image_worker/__init__.py

# Bake EasyOCR model weights into the image (en, de, tr, ru, ar)
RUN python - <<'EOF'
import easyocr, os
out = "/app/models/image/easyocr"
os.makedirs(out, exist_ok=True)
for langs in [['en', 'de', 'tr'], ['ru', 'en'], ['ar', 'en']]:
    print(f"Downloading EasyOCR models for: {langs}")
    easyocr.Reader(langs, gpu=False, model_storage_directory=out, download_enabled=True)
print("EasyOCR models saved to", out)
EOF

ENV PYTHONPATH=/app:/app/shared_libs \
    MODELS_PATH=/app/models \
    PYTHONUNBUFFERED=1
