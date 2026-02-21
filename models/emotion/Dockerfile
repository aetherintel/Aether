# models/emotion/Dockerfile
# Downloads custom german-emotions model from a GitHub Release.
# Requires build arg: GITHUB_TOKEN
FROM python:3.11-slim AS builder

ARG GITHUB_TOKEN
ARG GITHUB_REPOSITORY=aetherintel/aether
ARG MODEL_RELEASE_TAG=models-v1

WORKDIR /app
COPY emotion_model_downloader.py .

RUN GITHUB_TOKEN=${GITHUB_TOKEN} \
    GITHUB_REPOSITORY=${GITHUB_REPOSITORY} \
    MODEL_RELEASE_TAG=${MODEL_RELEASE_TAG} \
    python emotion_model_downloader.py

FROM alpine:latest
COPY --from=builder /app/emotion/german-emotions /models/emotion/german-emotions
CMD ["tail", "-f", "/dev/null"]
