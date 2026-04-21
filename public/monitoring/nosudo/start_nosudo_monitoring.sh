#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$ROOT/bin"
LOG_DIR="$ROOT/logs"
RUN_DIR="$ROOT/run"
mkdir -p "$LOG_DIR" "$RUN_DIR" "$ROOT/data/grafana" "$ROOT/data/grafana/plugins" "$ROOT/grafana/provisioning/plugins" "$ROOT/grafana/provisioning/alerting"
RENDER_DIR="$RUN_DIR/rendered"
mkdir -p "$RENDER_DIR/provisioning/dashboards" "$RENDER_DIR/provisioning/datasources"

PROM_VER="2.54.1"
GRAFANA_VER="11.2.2"
PROM_HOST="${PROM_HOST:-127.0.0.1}"
PROM_PORT="${PROM_PORT:-19090}"
GRAFANA_HOST="${GRAFANA_HOST:-0.0.0.0}"
GRAFANA_PORT="${GRAFANA_PORT:-13000}"
LM_EXPORTER_HOST="${LM_EXPORTER_HOST:-127.0.0.1}"
LM_EXPORTER_PORT="${LM_EXPORTER_PORT:-9401}"
FNOS_EXPORTER_HOST="${FNOS_EXPORTER_HOST:-127.0.0.1}"
FNOS_EXPORTER_PORT="${FNOS_EXPORTER_PORT:-9402}"
LM_EXPORTER_TOKEN="${LM_EXPORTER_TOKEN:-}"
LM_URL="${LM_URL:-http://127.0.0.1:1234/v1/models}"
LM_URL_FALLBACK="${LM_URL_FALLBACK:-http://127.0.0.1:1234/api/v0/models}"
PROM_BIN="$BIN_DIR/prometheus-${PROM_VER}.linux-amd64/prometheus"
GRAFANA_BIN="$BIN_DIR/grafana-v${GRAFANA_VER}/bin/grafana"
GRAFANA_CONFIG_RENDERED="$RENDER_DIR/grafana.ini"
DASHBOARDS_YML_RENDERED="$RENDER_DIR/provisioning/dashboards/dashboards.yml"
DATASOURCE_YML_RENDERED="$RENDER_DIR/provisioning/datasources/datasource.yml"

REMOTE_MAC_PORT="${REMOTE_MAC_PORT:-11300}"
LOCAL_GRAFANA_PORT="${LOCAL_GRAFANA_PORT:-13000}"
SSH_PORT="${SSH_PORT:-22}"
MAC_SSH_TARGETS="${MAC_SSH_TARGETS:-jiangzhiming@10.198.251.140 jiangzhiming@jiangzhimingmac.local}"

if [[ ! -x "$PROM_BIN" || ! -x "$GRAFANA_BIN" ]]; then
  echo "Missing binaries, run: bash $ROOT/install_nosudo_monitoring.sh"
  exit 1
fi

stop_if_running() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" || true
      sleep 1
    fi
    rm -f "$pid_file"
  fi
}

stop_if_running "$RUN_DIR/fnos_transfer_exporter.pid"
stop_if_running "$RUN_DIR/lm_exporter.pid"
stop_if_running "$RUN_DIR/prometheus.pid"
stop_if_running "$RUN_DIR/grafana.pid"
stop_if_running "$RUN_DIR/reverse_grafana_tunnel.pid"
pkill -f "$ROOT/reverse_grafana_tunnel.sh" >/dev/null 2>&1 || true
pkill -f "ssh .* -R ${REMOTE_MAC_PORT}:127.0.0.1:${LOCAL_GRAFANA_PORT}" >/dev/null 2>&1 || true

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy NO_PROXY no_proxy
unset LM_URL LM_URL_FALLBACK
export LM_EXPORTER_HOST
export LM_EXPORTER_PORT
export LM_EXPORTER_TOKEN
export FNOS_EXPORTER_HOST
export FNOS_EXPORTER_PORT
export LM_URL
export LM_URL_FALLBACK
export REMOTE_MAC_PORT
export LOCAL_GRAFANA_PORT
export SSH_PORT
export MAC_SSH_TARGETS

sed -e "s#__ROOT__#$ROOT#g" -e "s#__PROVISIONING__#$RENDER_DIR/provisioning#g" "$ROOT/grafana.ini" > "$GRAFANA_CONFIG_RENDERED"
sed "s#__ROOT__#$ROOT#g" "$ROOT/grafana/provisioning/dashboards/dashboards.yml" > "$DASHBOARDS_YML_RENDERED"
cp "$ROOT/grafana/provisioning/datasources/datasource.yml" "$DATASOURCE_YML_RENDERED"

nohup setsid python3 "$ROOT/lm_exporter.py" > "$LOG_DIR/lm_exporter.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/lm_exporter.pid"

nohup setsid python3 "$ROOT/fnos_transfer_exporter.py" > "$LOG_DIR/fnos_transfer_exporter.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/fnos_transfer_exporter.pid"

nohup setsid "$PROM_BIN" \
  --web.listen-address=$PROM_HOST:$PROM_PORT \
  --config.file="$ROOT/prometheus.yml" \
  --storage.tsdb.path="$ROOT/data/prometheus" \
  > "$LOG_DIR/prometheus.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/prometheus.pid"

nohup env GF_SERVER_HTTP_ADDR=$GRAFANA_HOST GF_SERVER_HTTP_PORT=$GRAFANA_PORT setsid "$GRAFANA_BIN" server \
  --homepath "$BIN_DIR/grafana-v${GRAFANA_VER}" \
  --config "$GRAFANA_CONFIG_RENDERED" \
  > "$LOG_DIR/grafana.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/grafana.pid"

nohup setsid "$ROOT/reverse_grafana_tunnel.sh" > "$LOG_DIR/reverse_grafana_tunnel.nohup.log" 2>&1 < /dev/null &
echo $! > "$RUN_DIR/reverse_grafana_tunnel.pid"

sleep 2

echo "Started:"
echo "- lm_exporter PID $(cat "$RUN_DIR/lm_exporter.pid")"
echo "- fnos_transfer_exporter PID $(cat "$RUN_DIR/fnos_transfer_exporter.pid")"
echo "- prometheus PID $(cat "$RUN_DIR/prometheus.pid")"
echo "- grafana PID $(cat "$RUN_DIR/grafana.pid")"
echo "- reverse_tunnel PID $(cat "$RUN_DIR/reverse_grafana_tunnel.pid")"

echo "Health checks:"
curl -fsS http://127.0.0.1:9401/metrics >/dev/null && echo "- lm_exporter ok"
curl -fsS http://127.0.0.1:9402/metrics >/dev/null && echo "- fnos_transfer_exporter ok"
curl -fsS http://127.0.0.1:19090/-/healthy >/dev/null && echo "- prometheus ok"
curl -fsS http://127.0.0.1:13000/api/health >/dev/null && echo "- grafana ok"

echo "Access locally:"
echo "- Grafana: http://127.0.0.1:13000 (admin/admin123)"
echo "- Prometheus: http://127.0.0.1:19090"
echo "- Reverse Grafana on Mac: http://127.0.0.1:${REMOTE_MAC_PORT}"
