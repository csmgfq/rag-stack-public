# RAG Stack Architecture (Transit Mode)

## Primary runtime and monitoring
- Host-side existing services remain the source of truth:
  - Prometheus: `127.0.0.1:19090`
  - Grafana: `127.0.0.1:13000`
  - LM exporter: `127.0.0.1:9401`

## Docker/transit layer
- Container at `ssh -p 50001 root@3090-6.grifcc.top` runs:
  - Tailscale interface
  - proxy OpenAPI (`/status`, `/apply`)
  - socat mappings for externally reachable transit ports

## Contract checks
- Host health: `scripts/stack_healthcheck.sh`
- OpenAPI compatibility: `scripts/stack_verify_openapi.sh`

## Note
- Root-level `docker-compose.yml` is retained for optional future migration,
  but is not the default production path in current constraints.
