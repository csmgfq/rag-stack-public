#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/kb_build_index.py \
  --input-jsonl kb/processed/cleaned_kb.jsonl \
  --output-index kb/processed/simple_index.json
