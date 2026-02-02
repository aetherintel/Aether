FROM python:3.11-slim as downloader
RUN pip install huggingface_hub
WORKDIR /app
# llm_download.py is in the build context root (./models)
COPY llm_download.py .
# Download Qwen 2.5 Coder 0.5B
RUN python llm_download.py download --model qwen2.5-coder-0.5b-instruct

FROM alpine:latest
# Copy the downloaded model to the volume location
COPY --from=downloader /app/llm/qwen2.5-coder-0.5b-instruct.gguf /models/llm/qwen2.5-coder-0.5b-instruct.gguf
CMD ["tail", "-f", "/dev/null"]
