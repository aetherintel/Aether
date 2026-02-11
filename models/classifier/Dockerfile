# models/classifier/Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
RUN pip install --no-cache-dir transformers torch

COPY download_classifier.py .
RUN python download_classifier.py

FROM alpine:latest
COPY --from=builder /app/classifier/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 /models/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
CMD ["tail", "-f", "/dev/null"]