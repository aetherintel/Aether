# telegram_scraper/Dockerfile
FROM python:3.12

WORKDIR /app

COPY aether_lib /app/aether_lib
COPY telegram_scraper/requirements.txt .

# Install system dependencies for ffmpeg and Pillow
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt
COPY telegram_scraper/ .

ENV PYTHONPATH=/app

CMD ["rq", "worker", "telegram-jobs", "--url", "redis://redis:6379/0"]