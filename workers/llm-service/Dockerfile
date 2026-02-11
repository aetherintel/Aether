# workers/llm-service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

ARG USE_CUDA=false
RUN if [ "$USE_CUDA" = "true" ]; then \
      pip install llama-cpp-python --no-cache-dir --force-reinstall --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu122; \
    else \
      CMAKE_ARGS="-DGGML_AVX2=ON" pip install --no-cache-dir llama-cpp-python --force-reinstall; \
    fi

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]