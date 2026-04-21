#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"commit message\" [--push]"
  exit 1
fi

MSG="$1"
PUSH=0
if [[ "${2:-}" == "--push" ]]; then
  PUSH=1
fi

REPOS=(
  "/home/jiangzhiming/workspace/rag-stack-public"
  "/home/jiangzhiming/workspace/llm/rag"
)

for repo in "${REPOS[@]}"; do
  if [[ ! -d "$repo/.git" ]]; then
    echo "[skip] $repo (not a git repo)"
    continue
  fi
  echo "[repo] $repo"
  cd "$repo"
  if [[ -z "$(git status --porcelain)" ]]; then
    echo "  no changes"
    continue
  fi
  git add -A
  git commit -m "$MSG"
  echo "  committed: $(git rev-parse --short HEAD)"
  if [[ "$PUSH" -eq 1 ]]; then
    git push
    echo "  pushed"
  fi
  echo
 done
