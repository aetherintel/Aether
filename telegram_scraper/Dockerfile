FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY telegram_job telegram_job
ENTRYPOINT ["python", "-m", "telegram_job.entry"]
