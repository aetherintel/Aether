#!/usr/bin/env bash

# URL to wait for
host="${KEYCLOAK_URL}"

# Wait until the URL is reachable
until curl -s "$host" >/dev/null; do
  echo "Waiting for $host..."
  sleep 2
done

# Run passed arguments (e.g. uvicorn main:app ...)
exec "$@"