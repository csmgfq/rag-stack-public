# rag-stack-public

一个面向本地 / 私有部署场景的最小化 RAG 基础设施模板仓库。

当前内容聚焦于两部分：

- `qdrant/`
  - 本地向量数据库配置模板
- `monitoring/`
  - 监控目录骨架，供后续补充 Prometheus / Grafana / exporter 配置

## 设计原则

- 只保留可公开分享的模板、目录结构和通用配置
- 不提交本地二进制、日志、数据库、索引数据和运行状态
- 不包含个人主机、账号、密码、令牌、内网地址等敏感信息

## 当前目录

```text
rag-stack-public/
├── monitoring/
│   ├── grafana/
│   ├── prometheus/
│   ├── scripts/
│   └── textfile/
└── qdrant/
    └── config.yaml
```

## Qdrant

配置文件：

- `qdrant/config.yaml`

默认使用相对路径存储数据：

```yaml
storage:
  storage_path: ./data/qdrant
```

这样可以避免把用户本地绝对路径写进仓库。

## 不会上传的内容

以下内容被视为本地运行产物，不会提交到仓库：

- `bin/`
- `data/`
- `logs/`
- `*.log`
- `*.pid`
- `*.db`

## 后续建议

如果你要把这个仓库扩展成完整的可复现实验模板，可以继续补充：

1. Qdrant 启动脚本
2. Docker Compose 或 systemd 配置
3. Prometheus 抓取配置
4. Grafana provisioning 模板
5. 示例数据导入脚本
