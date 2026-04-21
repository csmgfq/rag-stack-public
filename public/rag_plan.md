# RAG Plan v3 (Docker Direct to Tailscale / FNOS)

## Scope
- Default topology uses direct Tailscale P2P from server/container to FNOS.
- Personal PC relay is fallback only, not primary path.

## Architecture
1. Runtime
- LM Studio single-GPU serving with alias-based routing (`rag-main`, `rag-fallback`).
- Runtime knobs are env-based (model, context, parallelism, GPU binding).

2. Retrieval
- Qdrant as primary vector store.
- Redis L1 exact cache first, semantic cache extensibility reserved.

3. Network
- Host-local services are bridged into container and exposed on container Tailscale IP.
- Port mappings are managed through OpenAPI control plane.

## Backup Policy
- Small changes: no backup required.
- Major changes: backup required before/after release.

Major changes include:
- New features or large refactors.
- Port-forwarding strategy changes.
- Index/cache/runtime schema-level changes.

## Backup Path
- Primary: source -> FNOS direct stream.
- Optional mirror: FNOS primary path -> mounted cloud disk path.
- Verification: source/destination hash match; mirror quick/full verify as needed.

## Delivery Rule
- Update plan + skills in both repositories together.
- For minor updates: git commit only.
- For major updates: git commit + backup workflow.
