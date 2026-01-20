FROM python:3.11-slim as downloader
RUN pip install huggingface_hub
WORKDIR /app
# llm_download.py is in the build context root (./models)
COPY llm_download.py .
# Download Llama-3.2-1B
RUN python llm_download.py download --model llama3.2-1b-q4

FROM alpine:latest
# Copy the downloaded model to the volume location
COPY --from=downloader /app/llm/llama3.2-1b-q4.gguf /models/llm/llama3.2-1b-q4.gguf
CMD ["tail", "-f", "/dev/null"]
