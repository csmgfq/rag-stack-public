---
name: backup-fnos-workflow
description: Use this skill when you need repeatable backup operations that stream server/container artifacts directly to FNOS over Tailscale, with destination layout control and SHA256 verification.
---

# Backup FNOS Workflow

## Overview
This skill standardizes direct remote-to-remote backups to FNOS without local staging. It is designed for the `3090-6` host + `50001` container workflow and keeps outputs in date-based folders, with optional mirror copy to mounted cloud storage.

## When To Use
- You need to back up host artifacts from `/home/jiangzhiming/backups/<tag>`.
- You need to back up container artifacts from `/root/backups/<tag>` via `-p 50001`.
- You want one command that discovers latest backup tags, transfers to FNOS, and verifies checksums.

## Backup Trigger Policy
- Minor changes: do not run backup workflow.
- Major changes: run this workflow before/after release as needed.

Major changes include:
- Feature-level updates or large refactors.
- Port-forwarding/routing strategy changes.
- Index/cache/runtime schema-level configuration changes.

## Workflow
1. Confirm network reachability to FNOS (`admin@100.109.127.77`) and source hosts.
2. Run `scripts/run_backup_to_fnos.sh` in `--dry-run` mode first.
3. Run the real transfer.
4. Review script output for `HASH_MATCH` lines.
5. Keep destination under date folders: `<fnos_base>/<YYYYMMDD>/{server,container}`.
6. If needed, enable `--mirror-base` to duplicate backup into mounted Quark path and verify hashes.

## Command
```bash
bash scripts/run_backup_to_fnos.sh --dry-run
bash scripts/run_backup_to_fnos.sh
bash scripts/run_backup_to_fnos.sh --mirror-base /vol02/1000-1-9025b335/rag-stack-backups
bash scripts/run_backup_to_fnos.sh --mirror-base /vol02/1000-1-9025b335/rag-stack-backups --mirror-verify-mode quick
```

## Common Overrides
```bash
bash scripts/run_backup_to_fnos.sh \
  --date 20260421 \
  --fnos-host admin@100.109.127.77 \
  --fnos-base /vol2/1000/backups/rag-stack
```

## Resources
- Script details and flags: `references/usage.md`
- Executable workflow: `scripts/run_backup_to_fnos.sh`
