# RAG Stack Public Plan (Transit-first)

- Keep host runtime/monitoring as primary service path.
- Use docker/tailscale layer as transit + control plane.
- Verify by: host health ports + proxy OpenAPI (`/status`, `/apply`).
- Keep all sensitive values out of repo; use environment variables at runtime.
