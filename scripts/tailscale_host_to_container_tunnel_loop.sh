#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="${LOG_FILE:-/home/jiangzhiming/workspace/rag-stack/logs/tailscale_tunnel.log}"
while true; do
  echo "[$(date '+%F %T')] starting host->container ssh reverse tunnel" >> "$LOG_FILE"
  ssh -N \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=20 \
    -o ServerAliveCountMax=3 \
    -o TCPKeepAlive=yes \
    -o StrictHostKeyChecking=accept-new \
    -p 50001 \
    -R 51234:127.0.0.1:1234 \
    -R 56333:127.0.0.1:6333 \
    -R 56334:127.0.0.1:6334 \
    -R 59090:127.0.0.1:19090 \
    -R 59401:127.0.0.1:9401 \
    root@127.0.0.1 >> "$LOG_FILE" 2>&1 || true
  echo "[$(date '+%F %T')] tunnel exited, retry in 2s" >> "$LOG_FILE"
  sleep 2
done
