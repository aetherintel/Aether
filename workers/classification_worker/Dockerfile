FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY workers/classification_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aether_lib /app/aether_lib
COPY workers/classification_worker/*.py ./workers/classification_worker/

RUN touch /app/workers/__init__.py && \
    touch /app/workers/classification_worker/__init__.py

# Bake mDeBERTa-v3 multilingual NLI model into the image
RUN python - <<'EOF'
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import os
repo = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
out = "/app/models/classifier/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
os.makedirs(out, exist_ok=True)
print(f"Downloading {repo} ...")
AutoTokenizer.from_pretrained(repo).save_pretrained(out)
AutoModelForSequenceClassification.from_pretrained(repo).save_pretrained(out)
print(f"Model saved to {out}")
EOF

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/shared_libs \
    MODELS_PATH=/app/models
