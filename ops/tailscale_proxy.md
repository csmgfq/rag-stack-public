# Tailscale Proxy Control Plane

Control-plane entrypoint is kept under:
`/home/jiangzhiming/workspace/rag-stack/tailscale-forwarding/tailscale-proxy`

## API
- `GET /status`
- `POST /apply`

Default URL in current environment:
- `http://100.66.142.110:18080`

## Host-to-container reverse tunnel
Use:
- `scripts/tailscale_host_to_container_tunnel.sh`
- `scripts/tailscale_host_to_container_tunnel_loop.sh`
