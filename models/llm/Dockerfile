# Distroless model container
FROM python:3.11-slim as builder

WORKDIR /build

RUN pip install --no-cache-dir huggingface_hub

COPY llm_download.py .

# Download specific model
RUN python llm_download.py download --model qwen2.5-7b-instruct-q4

FROM alpine:latest
WORKDIR /models/llm

# Copy from builder
COPY --from=builder /models/llm/qwen2.5-7b-instruct-q4_k_m.gguf .

# Create a volume to share this directory
VOLUME /models/llm

CMD ["tail", "-f", "/dev/null"]
