# Usage Reference

## Script
`bash scripts/run_backup_to_fnos.sh`

## Defaults
- `FNOS_HOST=admin@100.109.127.77`
- `FNOS_BASE=/vol2/1000/backups/rag-stack`
- `MIRROR_BASE=` (optional, e.g. `/vol02/1000-1-9025b335/rag-stack-backups`)
- `MIRROR_VERIFY_MODE=quick` (`quick` compares filename+size, `full` computes SHA256)
- `HOST_SSH=jiangzhiming@3090-6.grifcc.top`
- `HOST_BACKUPS_ROOT=/home/jiangzhiming/backups`
- `CONTAINER_SSH=root@3090-6.grifcc.top`
- `CONTAINER_SSH_PORT=50001`
- `CONTAINER_BACKUPS_ROOT=/root/backups`
- `DATE=$(date +%Y%m%d)`

## Notes
- Container SSH usually prompts for password unless key auth is configured.
- The workflow uses tar streaming from source to FNOS directly, not local staging.
- Hash verification compares source and destination by filename-level SHA256.
- If `--mirror-base` is set, the script copies backup folders inside FNOS and verifies mirror hashes too.
- For slow cloud-mounted filesystems, keep `--mirror-verify-mode quick` to avoid long blocking hash reads.
