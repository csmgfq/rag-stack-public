#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"commit message\" [--push] [--proxy-url http://127.0.0.1:17897]"
  exit 1
fi

MSG="$1"
shift || true
PUSH=0
PROXY_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push) PUSH=1; shift ;;
    --proxy-url) PROXY_URL="${2:-}"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

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
  else
    git add -A
    git commit -m "$MSG"
    echo "  committed: $(git rev-parse --short HEAD)"
  fi

  if [[ "$PUSH" -eq 1 ]]; then
    if [[ -n "$PROXY_URL" ]]; then
      git -c http.proxy="$PROXY_URL" -c https.proxy="$PROXY_URL" push
    else
      git push
    fi
    echo "  pushed"
  fi
  echo
 done
