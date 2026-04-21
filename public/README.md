# Public Upload Bundle

This `public/` folder is reserved for uploading artifacts to remote environments.
It should contain only deployable/syncable materials and must not include local
runtime state or sensitive secrets.

## Included
- `monitoring/nosudo/` (scripts + configs only)
- `tailscale-forwarding/`
- `skills/backup-fnos-workflow/` (parameterized, no hardcoded secrets)
- `rag_plan.md`

## Excluded
- local databases, logs, pids, caches
- generated benchmark reports
- credentials, tokens, private host secrets
