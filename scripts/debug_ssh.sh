#!/bin/bash
set -e

# Load exact unformatted vars
if [ -f .env.remote.connection ]; then
  # Use 'source' but print each var
  cat .env.remote.connection
  source .env.remote.connection
else
  echo ".env.remote.connection missing"
  exit 1
fi

echo "--- Loaded Variables ---"
echo "VAST_IP: '$VAST_IP'"
echo "VAST_PORT: '$VAST_PORT'"
echo "SSH_KEY_PATH: '$SSH_KEY_PATH'"
echo "---"

if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "ERROR: File '$SSH_KEY_PATH' does not exist."
    ls -l "$SSH_KEY_PATH"
else
    echo "FILE EXISTS: $(ls -l "$SSH_KEY_PATH")"
fi

echo "--- Attempting SSH ---"
# Use -v for verbose output
ssh -v -p "$VAST_PORT" -i "$SSH_KEY_PATH" root@"$VAST_IP" uptime
