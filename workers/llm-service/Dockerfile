# workers/llm-service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN CMAKE_ARGS="-DGGML_AVX2=ON" pip install --no-cache-dir llama-cpp-python --upgrade --force-reinstall --no-cache-dir
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]