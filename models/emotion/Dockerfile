# models/emotion/Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
RUN pip install --no-cache-dir transformers torch

COPY emotion_model_downloader.py .
RUN python emotion_model_downloader.py

FROM alpine:latest
COPY --from=builder /app/emotion/german-emotions /models/emotion/german-emotions
CMD ["tail", "-f", "/dev/null"]