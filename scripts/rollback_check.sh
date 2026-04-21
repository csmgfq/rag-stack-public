#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

bash scripts/stack_status.sh
bash scripts/stack_healthcheck.sh

echo "[rollback_check] legacy monitoring + transit openapi still healthy"
