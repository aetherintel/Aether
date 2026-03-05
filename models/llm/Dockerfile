# Optimized model container to save disk space
FROM python:3.11-slim

WORKDIR /models/llm

# Install dependencies
RUN pip install --no-cache-dir huggingface_hub && \
    apt-get update && apt-get install -y rsync && \
    rm -rf /var/lib/apt/lists/*

COPY llm_download.py .

# Download model DIRECTLY to the final location to avoid intermediate layer duplication
RUN python llm_download.py download --model codestral-22b-v0.1-q4 && \
    rm -rf /root/.cache/huggingface

# Create volume
VOLUME /models/llm

# Copy to volume on startup (if using named volume)
CMD ["rsync", "-av", "--ignore-existing", "/models/llm/", "/models/llm_vol/"]
