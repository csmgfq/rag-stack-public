#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

CHAT_EXPORT="${KB_CHAT_EXPORT:-$ROOT_DIR/kb/raw/chat-export-1776788331981.json}"
RAG_MARKDOWN="${KB_MARKDOWN_FILE:-$ROOT_DIR/kb/raw/鱼皮-rag-概念技术解答.md}"

python3 scripts/kb_clean_data.py \
  --chat-export "$CHAT_EXPORT" \
  --markdown "$RAG_MARKDOWN" \
  --out-jsonl kb/processed/cleaned_kb.jsonl \
  --out-preview docs/kb_cleaning_preview.md
