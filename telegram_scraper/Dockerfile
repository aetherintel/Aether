# telegram_scraper/Dockerfile
FROM python:3.12

WORKDIR /app

COPY aether_lib /app/aether_lib
COPY telegram_scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY telegram_scraper/ .

ENV PYTHONPATH=/app

CMD ["rq", "worker", "telegram-jobs", "--url", "redis://redis:6379/0"]