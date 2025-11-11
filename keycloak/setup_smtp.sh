#!/bin/bash
set -e

# Starte Keycloak im Hintergrund
/opt/keycloak/bin/kc.sh start-dev --import-realm &
KC_PID=$!

# Warte bis Keycloak bereit ist
until curl -sf http://localhost:8080/health/ready > /dev/null 2>&1; do
  echo "Waiting for Keycloak..."
  sleep 2
done

# Login als Admin
/opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user "$KEYCLOAK_ADMIN" \
  --password "$KEYCLOAK_ADMIN_PASSWORD"

# SMTP konfigurieren
/opt/keycloak/bin/kcadm.sh update realms/HotTopics -s "smtpServer.host=smtp.strato.de" \
  -s "smtpServer.port=587" \
  -s "smtpServer.from=$SMTP_USER" \
  -s "smtpServer.user=$SMTP_USER" \
  -s "smtpServer.password=$SMTP_PASSWORD" \
  -s "smtpServer.auth=true" \
  -s "smtpServer.starttls=true" \
  -s "smtpServer.ssl=false"

echo "SMTP configured successfully"

# Halte Keycloak laufend
wait $KC_PID