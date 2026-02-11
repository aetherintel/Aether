# models/translation/Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
RUN pip install --no-cache-dir transformers torch sentencepiece

COPY translation_model_downloader.py .
RUN python translation_model_downloader.py

FROM alpine:latest
# Copy from builder
COPY --from=builder /app/translation/nllb-200-distilled-600M /models/nllb-200-distilled-600M
CMD ["tail", "-f", "/dev/null"]