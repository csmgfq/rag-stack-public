#!/usr/bin/env bash
set -euo pipefail

CONTAINER_SSH_HOST="${CONTAINER_SSH_HOST:-127.0.0.1}"
CONTAINER_SSH_PORT="${CONTAINER_SSH_PORT:-50001}"
CONTAINER_SSH_USER="${CONTAINER_SSH_USER:-root}"
PROXY_URL="${TAILSCALE_PROXY_URL:-http://100.66.142.110:18080}"

SSH_TARGET="${CONTAINER_SSH_USER}@${CONTAINER_SSH_HOST}"

ssh -o StrictHostKeyChecking=accept-new -p "$CONTAINER_SSH_PORT" "$SSH_TARGET" /bin/bash -s -- "$PROXY_URL" <<'REMOTE'
python3 - "$1" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip('/')
openapi = json.load(urllib.request.urlopen(base + '/openapi.json', timeout=5))
paths = openapi.get('paths', {})
required = ['/status', '/apply', '/api/v1/status', '/api/v1/apply']
missing = [p for p in required if p not in paths]
if missing:
    raise SystemExit('missing OpenAPI paths: ' + ', '.join(missing))
status = json.load(urllib.request.urlopen(base + '/status', timeout=5))
if 'tailscale_ip' not in status or 'entries' not in status:
    raise SystemExit('status payload missing required keys')
print('OPENAPI_OK')
print('STATUS_OK entries=', len(status.get('entries', [])))
PY
REMOTE
