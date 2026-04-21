#!/usr/bin/env bash
set -euo pipefail

curl -fsS http://127.0.0.1:19090/-/healthy >/dev/null
curl -fsS http://127.0.0.1:13000/api/health >/dev/null
curl -fsS http://127.0.0.1:9401/metrics >/dev/null

bash "$(cd "$(dirname "$0")" && pwd)/stack_verify_openapi.sh" >/dev/null

echo "[stack_healthcheck] all checks passed (host ports + transit OpenAPI)"
