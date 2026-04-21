#!/usr/bin/env bash
set -euo pipefail

echo "== Host monitoring processes =="
ps -ef | grep -Ei "monitoring/nosudo/(lm_exporter|fnos_transfer_exporter|bin/prometheus|bin/grafana)|reverse_grafana_tunnel" | grep -v grep || true

echo
for p in 19090 13000 9401; do
  if timeout 1 bash -lc "</dev/tcp/127.0.0.1/$p" 2>/dev/null; then
    echo "host port $p: open"
  else
    echo "host port $p: closed"
  fi
done

echo
echo "== Transit OpenAPI status =="
ssh -o StrictHostKeyChecking=accept-new -p 50001 root@127.0.0.1 \
  "curl -m 3 -fsS http://100.66.142.110:18080/status" || true
