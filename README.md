# rag-stack-public

一个面向本地 / 私有部署场景的最小化 RAG 基础设施模板仓库。

当前内容聚焦于三部分：

- `qdrant/`
  - 本地向量数据库配置模板
- `monitoring/`
  - 监控目录骨架，供后续补充 Prometheus / Grafana / exporter 配置
- `runtime/`
  - LM Studio 单卡运行 + 模型别名路由 + L1 缓存的可扩展运行时模板

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
├── qdrant/
│   └── config.yaml
├── runtime/
│   ├── model_profiles.json
│   ├── launcher.py
│   ├── router.py
│   ├── cache.py
│   └── config.py
├── scripts/
│   ├── start_single_gpu_runtime.sh
│   ├── smoke_test_runtime.sh
│   └── runtime_env.example
└── tests/
    └── test_runtime.py
```

## Qdrant

配置文件：

- `qdrant/config.yaml`

默认使用相对路径存储数据：

```yaml
storage:
  storage_path: ./data/qdrant
```

## Runtime 快速开始

```bash
cd /home/jiangzhiming/workspace/rag-stack-public
bash scripts/start_single_gpu_runtime.sh
```

默认行为：

- 以 `CUDA_VISIBLE_DEVICES=<gpu_binding>` 固定单卡。
- 加载模型别名：`rag-main`（16K）和 `rag-fallback`（8K）。
- 对外提供 OpenAI 兼容路由端点：`/v1/chat/completions`。

## 不会上传的内容

以下内容被视为本地运行产物，不会提交到仓库：

- `bin/`
- `data/`
- `logs/`
- `*.log`
- `*.pid`
- `*.db`

## 后续建议

1. 增加语义缓存（L2）作为可选插件。
2. 增加多实例路由策略（按任务路由到 `rag-fast` / `rag-longctx`）。
3. 对接 Prometheus 指标暴露路由命中率与缓存命中率。
