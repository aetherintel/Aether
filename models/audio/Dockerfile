# models/audio/Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
RUN pip install --no-cache-dir openai-whisper

COPY audio_model_download.py .
# Script defaults to ./audio/whisper
RUN python audio_model_download.py --output-dir ./audio/whisper

FROM alpine:latest
COPY --from=builder /app/audio/whisper /models/whisper
CMD ["tail", "-f", "/dev/null"]