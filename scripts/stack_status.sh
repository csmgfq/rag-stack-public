#!/usr/bin/env bash
set -euo pipefail

PROXY_URL="${TAILSCALE_PROXY_URL:-http://100.66.142.110:18080}"

echo "== Host monitoring processes =="
ps -ef | grep -Ei "monitoring/nosudo/(lm_exporter|fnos_transfer_exporter|bin/prometheus|bin/grafana)|reverse_grafana_tunnel" | grep -v grep || true

echo
for p in 19090 13000 9401; do
  if timeout 1 bash -lc "</dev/tcp/127.0.0.1/$p" 2>/dev/null; then
    echo "host port $p: open"
  else
    echo "host port $p: closed (or not reachable from current namespace)"
  fi
done

echo
echo "== Transit OpenAPI status =="
curl -m 3 -fsS "$PROXY_URL/status" || true
