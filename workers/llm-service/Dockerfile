# workers/llm-service/Dockerfile
FROM nvidia/cuda:12.2.2-runtime-ubuntu22.04

WORKDIR /app

# Install Python and build dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    build-essential \
    cmake \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Symlink python3 to python if not exists
RUN ln -s /usr/bin/python3.11 /usr/bin/python

COPY requirements.txt .

# ARG USE_CUDA=true
# Force CUDA installation for remote GPU worker
RUN pip install llama-cpp-python --no-cache-dir --force-reinstall --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu122

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]