FROM python:3.12

WORKDIR /

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy and set permissions for the wait script
COPY wait-for.sh /wait-for.sh
RUN chmod +x /wait-for.sh

EXPOSE 8000

CMD ["/wait-for.sh", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

