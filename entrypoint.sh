#!/bin/sh
set -e

run_bot() {
  if [ "$DEV" = "1" ]; then
    exec watchmedo auto-restart --directory=/app/bot --pattern='*.py' --recursive -- python -m bot
  else
    exec python -m bot
  fi
}

if [ -n "$WEBHOOK_URL" ]; then
  run_bot
fi

# Local dev: start ngrok and use its URL as WEBHOOK_URL
ngrok http 8080 --log=stdout &
sleep 3
WEBHOOK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'] if d.get('tunnels') else '')")
if [ -z "$WEBHOOK_URL" ]; then
  echo "ngrok failed to start. Set NGROK_AUTHTOKEN in .env (get one at https://dashboard.ngrok.com/get-started/your-authtoken)" >&2
  exit 1
fi
export WEBHOOK_URL
run_bot
