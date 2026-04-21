#!/usr/bin/env bash
set -euo pipefail

STRICT_HOST_PORTS="${STRICT_HOST_PORTS:-false}"

port_fail=0
for u in "http://127.0.0.1:19090/-/healthy" "http://127.0.0.1:13000/api/health" "http://127.0.0.1:9401/metrics"; do
  if ! curl -fsS "$u" >/dev/null; then
    echo "[stack_healthcheck] warn host endpoint unreachable: $u"
    port_fail=1
  fi
done

if [[ "$STRICT_HOST_PORTS" == "true" && "$port_fail" -ne 0 ]]; then
  echo "[stack_healthcheck] host endpoint checks failed under STRICT_HOST_PORTS=true"
  exit 1
fi

bash "$(cd "$(dirname "$0")" && pwd)/stack_verify_openapi.sh" >/dev/null

echo "[stack_healthcheck] checks passed (OpenAPI required; host endpoints best-effort unless STRICT_HOST_PORTS=true)"
