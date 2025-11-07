FROM python:3.11-slim
WORKDIR /app/telegram_job

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY aether_lib /app/aether_lib
# Kopiere alles direkt ins WORKDIR
COPY telegram_job/*.py ./

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["rq", "worker", "--url", "redis://redis:6379/0", "telegram-jobs"]