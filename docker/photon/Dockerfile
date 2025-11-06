# docker/photon/Dockerfile
FROM eclipse-temurin:17-jre-jammy

WORKDIR /photon

# Install curl for healthcheck
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Download latest Photon JAR
RUN curl -L https://github.com/komoot/photon/releases/download/0.5.0/photon-0.5.0.jar -o photon.jar

# Expose API port
EXPOSE 2322

# Start Photon
CMD ["java", "-Xmx2g", "-jar", "photon.jar"]