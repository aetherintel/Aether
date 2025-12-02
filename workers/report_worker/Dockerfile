FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for WeasyPrint (cairo, pango, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && apt-get clean

# Copy backend requirements (since we use backend code)
COPY backend/app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/app /app/app

# Copy worker code
COPY workers/report_worker /app/workers/report_worker

# Set PYTHONPATH to include app
ENV PYTHONPATH=/app:/app/app

# Start RQ worker
CMD ["rq", "worker", "report-jobs", "--url", "redis://redis:6379"]
