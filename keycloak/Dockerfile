# Dockerfile.keycloak
FROM quay.io/keycloak/keycloak:24.0.2

# Install the Postgres driver and build the config
RUN /opt/keycloak/bin/kc.sh build --db=postgres

# Kopiere CLI-Script
COPY configure-smtp.sh /opt/keycloak/configure-smtp.sh
RUN chmod +x /opt/keycloak/configure-smtp.sh

COPY exports/ /opt/keycloak/data/import/

ENTRYPOINT ["/opt/keycloak/configure-smtp.sh"]