# Tailscale Forwarding + OpenAPI 管理

这套文件用于把宿主机本地服务通过容器 Tailscale IP 暴露出去，并用 OpenAPI 管理映射。

## 目录
- `host-scripts/`
  - `tailscale_host_to_container_tunnel.sh`
  - `tailscale_host_to_container_tunnel_loop.sh`
- `tailscale-proxy/`
  - `proxy_api.py` FastAPI 控制面
  - `proxy_ctl.py` socat 进程控制
  - `proxies.json` 映射配置
  - `start_socat_proxies.sh` / `stop_socat_proxies.sh`

## 访问示例
- OpenAPI 文档: `http://<container_ts_ip>:18080/docs`
- 状态: `GET /status`
- 应用配置: `POST /apply`

## 安全建议
- `proxies.json` 不要写账号密码。
- 生产环境建议给 API 增加认证或仅在 Tailscale ACL 允许设备访问。
