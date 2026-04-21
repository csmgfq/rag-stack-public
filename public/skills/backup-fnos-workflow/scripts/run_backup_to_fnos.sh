#!/usr/bin/env bash
set -euo pipefail

FNOS_HOST="admin@100.109.127.77"
FNOS_BASE="/vol2/1000/backups/rag-stack"
MIRROR_BASE=""
MIRROR_VERIFY_MODE="quick"
HOST_SSH="jiangzhiming@3090-6.grifcc.top"
HOST_BACKUPS_ROOT="/home/jiangzhiming/backups"
CONTAINER_SSH="root@3090-6.grifcc.top"
CONTAINER_SSH_PORT="50001"
CONTAINER_BACKUPS_ROOT="/root/backups"
DATE_TAG="$(date +%Y%m%d)"
HOST_BACKUP_DIR=""
CONTAINER_BACKUP_DIR=""
DRY_RUN=0

log() { printf '[backup-fnos] %s\n' "$*"; }
run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
  else
    eval "$@"
  fi
}

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]
  --fnos-host <user@host>
  --fnos-base <path>
  --mirror-base <path on FNOS, optional>
  --mirror-verify-mode <quick|full> (default: quick)
  --date <YYYYMMDD>
  --host-ssh <user@host>
  --host-backups-root <path>
  --host-backup-dir <absolute path>
  --container-ssh <user@host>
  --container-port <port>
  --container-backups-root <path>
  --container-backup-dir <absolute path>
  --dry-run
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fnos-host) FNOS_HOST="$2"; shift 2 ;;
    --fnos-base) FNOS_BASE="$2"; shift 2 ;;
    --mirror-base) MIRROR_BASE="$2"; shift 2 ;;
    --mirror-verify-mode) MIRROR_VERIFY_MODE="$2"; shift 2 ;;
    --date) DATE_TAG="$2"; shift 2 ;;
    --host-ssh) HOST_SSH="$2"; shift 2 ;;
    --host-backups-root) HOST_BACKUPS_ROOT="$2"; shift 2 ;;
    --host-backup-dir) HOST_BACKUP_DIR="$2"; shift 2 ;;
    --container-ssh) CONTAINER_SSH="$2"; shift 2 ;;
    --container-port) CONTAINER_SSH_PORT="$2"; shift 2 ;;
    --container-backups-root) CONTAINER_BACKUPS_ROOT="$2"; shift 2 ;;
    --container-backup-dir) CONTAINER_BACKUP_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

DEST_ROOT="${FNOS_BASE}/${DATE_TAG}"
DEST_SERVER="${DEST_ROOT}/server"
DEST_CONTAINER="${DEST_ROOT}/container"
MIRROR_ROOT=""
MIRROR_SERVER=""
MIRROR_CONTAINER=""
if [[ -n "$MIRROR_BASE" ]]; then
  MIRROR_ROOT="${MIRROR_BASE%/}/${DATE_TAG}"
  MIRROR_SERVER="${MIRROR_ROOT}/server"
  MIRROR_CONTAINER="${MIRROR_ROOT}/container"
fi

if [[ "$MIRROR_VERIFY_MODE" != "quick" && "$MIRROR_VERIFY_MODE" != "full" ]]; then
  log "Invalid --mirror-verify-mode: ${MIRROR_VERIFY_MODE} (use quick|full)"
  exit 1
fi

if [[ -z "$HOST_BACKUP_DIR" ]]; then
  log "Discovering latest host backup directory from ${HOST_SSH}:${HOST_BACKUPS_ROOT}"
  HOST_BACKUP_DIR="$(ssh "$HOST_SSH" "ls -1dt '${HOST_BACKUPS_ROOT}'/* 2>/dev/null | head -n1")"
fi

if [[ -z "$CONTAINER_BACKUP_DIR" ]]; then
  log "Discovering latest container backup directory from ${CONTAINER_SSH}:${CONTAINER_BACKUPS_ROOT}"
  CONTAINER_BACKUP_DIR="$(ssh -p "$CONTAINER_SSH_PORT" "$CONTAINER_SSH" "ls -1dt '${CONTAINER_BACKUPS_ROOT}'/* 2>/dev/null | head -n1")"
fi

if [[ -z "$HOST_BACKUP_DIR" || -z "$CONTAINER_BACKUP_DIR" ]]; then
  log "Failed to discover backup source directories."
  exit 1
fi

log "Host source: ${HOST_BACKUP_DIR}"
log "Container source: ${CONTAINER_BACKUP_DIR}"
log "FNOS destination root: ${DEST_ROOT}"
if [[ -n "$MIRROR_BASE" ]]; then
  log "FNOS mirror root: ${MIRROR_ROOT}"
fi

run "ssh '$FNOS_HOST' \"mkdir -p '$DEST_SERVER' '$DEST_CONTAINER'\""

log "Streaming host backups directly to FNOS"
run "ssh '$HOST_SSH' \"cd '$HOST_BACKUP_DIR' && tar -cf - .\" | ssh '$FNOS_HOST' \"cd '$DEST_SERVER' && tar -xf -\""

log "Streaming container backups directly to FNOS"
run "ssh -p '$CONTAINER_SSH_PORT' '$CONTAINER_SSH' \"cd '$CONTAINER_BACKUP_DIR' && tar -cf - .\" | ssh '$FNOS_HOST' \"cd '$DEST_CONTAINER' && tar -xf -\""

if [[ -n "$MIRROR_BASE" ]]; then
  log "Mirroring primary backup to ${MIRROR_ROOT} (FNOS local copy)"
  run "ssh '$FNOS_HOST' \"mkdir -p '$MIRROR_SERVER' '$MIRROR_CONTAINER' && find '$MIRROR_SERVER' -mindepth 1 -maxdepth 1 -exec rm -rf {} + && find '$MIRROR_CONTAINER' -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar -C '$DEST_SERVER' -cf - . | tar -C '$MIRROR_SERVER' --no-same-owner --no-same-permissions -xf - && tar -C '$DEST_CONTAINER' -cf - . | tar -C '$MIRROR_CONTAINER' --no-same-owner --no-same-permissions -xf -\""
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "Dry-run finished. No data transferred."
  exit 0
fi

log "Verifying SHA256 hashes for host artifacts"
HOST_SRC_HASHES="$(ssh "$HOST_SSH" "cd '$HOST_BACKUP_DIR' && find . -maxdepth 1 -type f -print0 | xargs -0 sha256sum | sed 's#  \./#  #' | sort")"
HOST_DST_HASHES="$(ssh "$FNOS_HOST" "cd '$DEST_SERVER' && find . -maxdepth 1 -type f -print0 | xargs -0 sha256sum | sed 's#  \./#  #' | sort")"
if [[ "$HOST_SRC_HASHES" == "$HOST_DST_HASHES" ]]; then
  log "HASH_MATCH server"
else
  log "HASH_MISMATCH server"
  diff <(printf '%s\n' "$HOST_SRC_HASHES") <(printf '%s\n' "$HOST_DST_HASHES") || true
  exit 2
fi

log "Verifying SHA256 hashes for container artifacts"
CONTAINER_SRC_HASHES="$(ssh -p "$CONTAINER_SSH_PORT" "$CONTAINER_SSH" "cd '$CONTAINER_BACKUP_DIR' && find . -maxdepth 1 -type f -print0 | xargs -0 sha256sum | sed 's#  \./#  #' | sort")"
CONTAINER_DST_HASHES="$(ssh "$FNOS_HOST" "cd '$DEST_CONTAINER' && find . -maxdepth 1 -type f -print0 | xargs -0 sha256sum | sed 's#  \./#  #' | sort")"
if [[ "$CONTAINER_SRC_HASHES" == "$CONTAINER_DST_HASHES" ]]; then
  log "HASH_MATCH container"
else
  log "HASH_MISMATCH container"
  diff <(printf '%s\n' "$CONTAINER_SRC_HASHES") <(printf '%s\n' "$CONTAINER_DST_HASHES") || true
  exit 2
fi

if [[ -n "$MIRROR_BASE" ]]; then
  if [[ "$MIRROR_VERIFY_MODE" == "full" ]]; then
    log "Verifying SHA256 hashes for mirror artifacts (full)"
    MIRROR_SERVER_HASHES="$(ssh "$FNOS_HOST" "cd '$MIRROR_SERVER' && find . -maxdepth 1 -type f -print0 | xargs -0 sha256sum | sed 's#  \./#  #' | sort")"
    MIRROR_CONTAINER_HASHES="$(ssh "$FNOS_HOST" "cd '$MIRROR_CONTAINER' && find . -maxdepth 1 -type f -print0 | xargs -0 sha256sum | sed 's#  \./#  #' | sort")"

    if [[ "$HOST_DST_HASHES" == "$MIRROR_SERVER_HASHES" ]]; then
      log "HASH_MATCH mirror-server"
    else
      log "HASH_MISMATCH mirror-server"
      diff <(printf '%s\n' "$HOST_DST_HASHES") <(printf '%s\n' "$MIRROR_SERVER_HASHES") || true
      exit 2
    fi

    if [[ "$CONTAINER_DST_HASHES" == "$MIRROR_CONTAINER_HASHES" ]]; then
      log "HASH_MATCH mirror-container"
    else
      log "HASH_MISMATCH mirror-container"
      diff <(printf '%s\n' "$CONTAINER_DST_HASHES") <(printf '%s\n' "$MIRROR_CONTAINER_HASHES") || true
      exit 2
    fi
  else
    log "Verifying mirror artifacts (quick: filename + size)"
    SERVER_PRIMARY_LIST="$(ssh "$FNOS_HOST" "cd '$DEST_SERVER' && find . -maxdepth 1 -type f -exec stat -c '%n %s' {} \\; | sed 's#^\\./##' | sort")"
    SERVER_MIRROR_LIST="$(ssh "$FNOS_HOST" "cd '$MIRROR_SERVER' && find . -maxdepth 1 -type f -exec stat -c '%n %s' {} \\; | sed 's#^\\./##' | sort")"
    CONTAINER_PRIMARY_LIST="$(ssh "$FNOS_HOST" "cd '$DEST_CONTAINER' && find . -maxdepth 1 -type f -exec stat -c '%n %s' {} \\; | sed 's#^\\./##' | sort")"
    CONTAINER_MIRROR_LIST="$(ssh "$FNOS_HOST" "cd '$MIRROR_CONTAINER' && find . -maxdepth 1 -type f -exec stat -c '%n %s' {} \\; | sed 's#^\\./##' | sort")"

    if [[ "$SERVER_PRIMARY_LIST" == "$SERVER_MIRROR_LIST" ]]; then
      log "QUICK_MATCH mirror-server"
    else
      log "QUICK_MISMATCH mirror-server"
      diff <(printf '%s\n' "$SERVER_PRIMARY_LIST") <(printf '%s\n' "$SERVER_MIRROR_LIST") || true
      exit 2
    fi

    if [[ "$CONTAINER_PRIMARY_LIST" == "$CONTAINER_MIRROR_LIST" ]]; then
      log "QUICK_MATCH mirror-container"
    else
      log "QUICK_MISMATCH mirror-container"
      diff <(printf '%s\n' "$CONTAINER_PRIMARY_LIST") <(printf '%s\n' "$CONTAINER_MIRROR_LIST") || true
      exit 2
    fi
  fi
fi

log "Backup workflow completed successfully."
log "Destination: ${DEST_ROOT}"
if [[ -n "$MIRROR_BASE" ]]; then
  log "Mirror: ${MIRROR_ROOT}"
fi
