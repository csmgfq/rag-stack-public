---
name: backup-fnos-workflow
description: Parameterized backup workflow to FNOS and optional mirror path, without hardcoded credentials.
---

# Backup FNOS Workflow (Public)

Use environment variables or CLI flags for all hostnames/accounts/paths.
Do not hardcode passwords, tokens, or private endpoints.

## Command
```bash
bash scripts/run_backup_to_fnos.sh --dry-run
bash scripts/run_backup_to_fnos.sh \
  --fnos-host <user@host> \
  --fnos-base <dest-path> \
  --host-ssh <user@host> \
  --container-ssh <user@host> --container-port <port>
```
