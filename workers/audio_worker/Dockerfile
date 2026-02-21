FROM python:3.11-slim

# System deps: ffmpeg for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY workers/audio_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt openai-whisper

COPY aether_lib /app/aether_lib
COPY workers/audio_worker/ /app/workers/audio_worker

RUN touch /app/workers/__init__.py && \
    touch /app/workers/audio_worker/__init__.py

# Bake Whisper model weights into the image
RUN python - <<'EOF'
import whisper, os
out = "/app/models/audio/whisper"
os.makedirs(out, exist_ok=True)
whisper.load_model("base", download_root=out)
print("Whisper base model saved to", out)
EOF

ENV PYTHONPATH=/app:/app/shared_libs:$PYTHONPATH \
    MODELS_PATH=/app/models \
    OMP_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2 \
    PYTHONUNBUFFERED=1
