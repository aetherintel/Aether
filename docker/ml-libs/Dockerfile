# docker/ml-libs/Dockerfile
FROM python:3.11-slim

WORKDIR /ml-libs

COPY docker/ml-libs/requirements.txt .

# Install to /ml-libs
RUN pip install --no-cache-dir --target=/ml-libs -r requirements.txt

CMD ["echo", "ML libs image built"]