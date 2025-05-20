# Dockerfile.keycloak
FROM quay.io/keycloak/keycloak:24.0.2

# Install the Postgres driver and build the config
RUN /opt/keycloak/bin/kc.sh build --db=postgres
