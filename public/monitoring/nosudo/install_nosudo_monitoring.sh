#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$ROOT/bin"
DATA_DIR="$ROOT/data"
mkdir -p "$BIN_DIR" "$DATA_DIR/grafana" "$ROOT/logs" "$ROOT/run"

PROM_VER="2.54.1"
GRAFANA_VER="11.2.2"

PROM_ARCHIVE="prometheus-${PROM_VER}.linux-amd64.tar.gz"
PROM_URL="https://github.com/prometheus/prometheus/releases/download/v${PROM_VER}/${PROM_ARCHIVE}"
PROM_DIR="$BIN_DIR/prometheus-${PROM_VER}.linux-amd64"

GRAF_ARCHIVE="grafana-${GRAFANA_VER}.linux-amd64.tar.gz"
GRAF_URL="https://dl.grafana.com/oss/release/${GRAF_ARCHIVE}"
GRAF_DIR="$BIN_DIR/grafana-v${GRAFANA_VER}"

echo "[1/4] Download Prometheus ${PROM_VER}"
if [[ ! -d "$PROM_DIR" ]]; then
  cd "$BIN_DIR"
  curl -fL "$PROM_URL" -o "$PROM_ARCHIVE"
  tar -xzf "$PROM_ARCHIVE"
fi

echo "[2/4] Download Grafana ${GRAFANA_VER}"
if [[ ! -d "$GRAF_DIR" ]]; then
  cd "$BIN_DIR"
  curl -fL "$GRAF_URL" -o "$GRAF_ARCHIVE"
  tar -xzf "$GRAF_ARCHIVE"
fi

echo "[3/4] Ensure executable bits"
chmod +x "$ROOT/lm_exporter.py"
chmod +x "$PROM_DIR/prometheus"
chmod +x "$GRAF_DIR/bin/grafana"

echo "[4/4] Done"
echo "Prometheus: $PROM_DIR/prometheus"
echo "Grafana: $GRAF_DIR/bin/grafana"
echo "Next: bash $ROOT/start_nosudo_monitoring.sh"
