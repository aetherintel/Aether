FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first (cache-friendly layer)
COPY workers/translation_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt huggingface_hub

# Copy worker source
COPY workers/translation_worker ./workers/translation_worker
COPY aether_lib /app/aether_lib

# Ensure package init files exist
RUN touch /app/workers/__init__.py && \
    touch /app/workers/translation_worker/__init__.py

# Download NLLB-200-distilled-600M model weights into the image
# This makes the image self-contained — no volume mounts or sidecars needed.
RUN python - <<'EOF'
from huggingface_hub import snapshot_download
import os
out = "/app/models/nllb-200-distilled-600M"
os.makedirs(out, exist_ok=True)
snapshot_download(
    repo_id="facebook/nllb-200-distilled-600M",
    local_dir=out,
    ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*", "rust_model*"],
)
print("Model downloaded to", out)
EOF

ENV PYTHONUNBUFFERED=1 \
    MODELS_PATH=/app/models \
    PYTHONPATH=/app:/app/workers:/app/aether_lib:/app/shared_libs
