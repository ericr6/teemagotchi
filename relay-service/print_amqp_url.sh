#!/usr/bin/env bash
# Wait for ngrok to publish the public TCP endpoint and print AMQP URL.
set -euo pipefail

RABBIT_USER=ai
RABBIT_PASS=supersecret
NGROK_CONTAINER=ngrok

echo "⏳ waiting for ngrok tunnel..."
for i in {1..40}; do
  # The wernight/ngrok image exposes port 4040 inside the *same* container
  # We'll use docker exec to curl it
  OUT=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null || true)
  PUBLIC_URL=$(echo "$OUT" | jq -r '.tunnels[]? | select(.proto=="tcp") | .public_url')
  if [[ $PUBLIC_URL == tcp://* ]]; then
    HOSTPORT=${PUBLIC_URL#tcp://} # strip scheme
    echo "✅ AMQP_URL: amqps://${RABBIT_USER}:${RABBIT_PASS}@${HOSTPORT}//"
    exit 0
  fi
  sleep 1
done

echo "❌ ngrok tunnel not found"
exit 1
