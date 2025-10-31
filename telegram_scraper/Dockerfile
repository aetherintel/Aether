FROM python:3.11-slim
WORKDIR /app/telegram_job

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere alles direkt ins WORKDIR
COPY telegram_job/*.py ./

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["rq", "worker", "--url", "--timeout", "6000", "redis://redis:6379/0", "telegram-jobs"]