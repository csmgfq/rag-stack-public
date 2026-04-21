#!/usr/bin/env bash
set -euo pipefail

CONTAINER_SSH_HOST="${CONTAINER_SSH_HOST:-127.0.0.1}"
CONTAINER_SSH_PORT="${CONTAINER_SSH_PORT:-50001}"
CONTAINER_SSH_USER="${CONTAINER_SSH_USER:-root}"

# Remote(for container) -> Local(host loopback service)
# container:51234 -> host:1234   (LM Studio)
# container:56333 -> host:6333   (Qdrant HTTP)
# container:56334 -> host:6334   (Qdrant gRPC)
# container:59090 -> host:19090  (Prometheus)
# container:59401 -> host:9401   (lm_exporter)
exec ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=20 \
  -o ServerAliveCountMax=3 \
  -o TCPKeepAlive=yes \
  -o StrictHostKeyChecking=accept-new \
  -p "$CONTAINER_SSH_PORT" \
  -R 51234:127.0.0.1:1234 \
  -R 56333:127.0.0.1:6333 \
  -R 56334:127.0.0.1:6334 \
  -R 59090:127.0.0.1:19090 \
  -R 59401:127.0.0.1:9401 \
  "$CONTAINER_SSH_USER@$CONTAINER_SSH_HOST"
