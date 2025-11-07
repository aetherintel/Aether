# backend/app/Dockerfile
FROM python:3.12

WORKDIR /app

# Copy shared lib (relativ zu Root)
COPY aether_lib /app/aether_lib

# Copy backend requirements (relativ zu Root)
COPY backend/app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code (relativ zu Root)
COPY backend/app/ .

# Copy wait script
COPY backend/app/wait-for.sh /wait-for.sh
RUN chmod +x /wait-for.sh

# Set PYTHONPATH
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["/wait-for.sh", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]