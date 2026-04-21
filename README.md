# rag-stack

Unified project root for runtime, monitoring, and tailscale forwarding.

Current mode is **transit-first**:
- Existing host runtime/monitoring remains primary.
- Docker layer is used as forwarding/control-plane transit.

## Entry points

```bash
cd /home/jiangzhiming/workspace/rag-stack
bash scripts/stack_up.sh
bash scripts/stack_status.sh
bash scripts/stack_healthcheck.sh
bash scripts/stack_down.sh --force-stop-legacy
```

## Layout

- `runtime/`: runtime router + launcher
- `monitoring/`: monitoring configs and legacy notes
- `tailscale-forwarding/`: proxy control plane and tunnel scripts
- `ops/`: operational runbooks
- `docs/`: architecture and migration docs
- `docker-compose.yml`: reserved for optional future full dockerization
