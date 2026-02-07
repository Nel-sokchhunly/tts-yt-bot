#!/bin/sh
set -e
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz";;
  aarch64|arm64) URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz";;
  *) echo "Unsupported arch: $ARCH"; exit 1;;
esac
curl -sSL "$URL" | tar xz -C /usr/local/bin
