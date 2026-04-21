# rag-stack-public

RAG 基础设施第二版汇总仓库（单仓入口，Transit-first 运行）。

这个仓库把三件事情统一在一起：
- Runtime：LM Studio 单卡路由、模型配置、轻量压测。
- Monitoring：Prometheus/Grafana/exporter 监看链路。
- Transit 控制面：Tailscale 转发与 OpenAPI（`/status`、`/apply`）。

当前默认策略是 **中转优先（Transit-first）**：
- 保持你现在已经跑着的主链路为主，不强制推翻成全容器。
- Docker/50001 容器主要作为中转与控制面入口。

## 1. 仓库结构

```text
rag-stack-public/
├── README.md
├── benchmark_lmstudio.py
├── docker-compose.yml                    # 预留：未来全容器化
├── runtime/                              # 路由与模型 profile
├── monitoring/                           # Prometheus/Grafana/exporters 配置
├── tailscale-forwarding/                 # 转发控制面与隧道脚本
├── scripts/
│   ├── stack_up.sh
│   ├── stack_down.sh
│   ├── stack_status.sh
│   ├── stack_healthcheck.sh
│   ├── stack_verify_openapi.sh
│   ├── start_single_gpu_runtime.sh
│   └── runtime_env.example
├── docs/
├── ops/
├── public/                               # 对外上传目录（仅分发内容）
└── skills/
    └── rag-stack-ops/
        └── SKILL.md                      # Codex 运维技能模板
```

## 2. 执行入口（本地 + 远端）

### 2.1 推荐入口

- 容器内主入口（当前可操作环境）：`/workspace/rag-stack-public`
- 登录方式（已配置 key 时）：

```bash
ssh -p 50001 root@3090-6.grifcc.top
cd /workspace/rag-stack-public
```

### 2.2 历史目录关系

- 当前汇总仓：`/workspace/rag-stack-public`
- 历史运行链路仍在：`/workspace/llm/rag`（由 `stack_*.sh` 按需调用）
- 原则：历史目录保留可回滚能力，但日常运维统一走本仓脚本。

## 3. 快速开始（建议照这个顺序）

### 3.1 启动

```bash
cd /workspace/rag-stack-public
bash scripts/stack_up.sh
```

行为说明：
- 脚本会尝试调用历史监看启动脚本（若存在）。
- 默认不做破坏性停服动作。

### 3.2 看状态

```bash
bash scripts/stack_status.sh
```

会检查：
- 监看关键进程。
- 主机端口：`19090`、`13000`、`9401`。
- Transit OpenAPI 的 `/status`。

### 3.3 健康检查（验收必跑）

```bash
bash scripts/stack_healthcheck.sh
```

检查项：
- `http://127.0.0.1:19090/-/healthy`
- `http://127.0.0.1:13000/api/health`
- `http://127.0.0.1:9401/metrics`
- OpenAPI 合规：`/status`、`/apply`、`/api/v1/status`、`/api/v1/apply`

### 3.4 停止（安全默认）

```bash
bash scripts/stack_down.sh
```

默认不会停止历史服务；确需停机时：

```bash
bash scripts/stack_down.sh --force-stop-legacy
```

## 4. Runtime（单卡）

你已经将多卡问题收敛到单卡运行，本仓沿用该策略。

### 4.1 准备环境变量

```bash
cp scripts/runtime_env.example scripts/runtime_env.sh
# 根据真实路径修改 runtime_env.sh
source scripts/runtime_env.sh
```

关键变量：
- `LMSTUDIO_BASE_URL`：默认 `http://127.0.0.1:1234/v1`
- `RAG_GPU_BINDING`：默认 `0`
- `RAG_ROUTER_PORT`：默认 `18000`

### 4.2 启动 runtime

```bash
bash scripts/start_single_gpu_runtime.sh
```

说明：
- 脚本会优先使用 `.venv-runtime`。
- 自动安装 `runtime/requirements.txt`。
- 启动 `runtime.launcher` + `uvicorn runtime.router:app`。

## 5. 轻量压测（只做可跑通验证）

```bash
cd /workspace/rag-stack-public
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1 \
LMSTUDIO_MODELS=google/gemma-4-e4b \
BENCH_SHORT_REQUESTS=2 \
BENCH_SHORT_CONCURRENCY=1 \
BENCH_LONG_REQUESTS=2 \
BENCH_LONG_CONCURRENCY=1 \
BENCH_LONG_CONTEXT_CHARS=6000 \
BENCH_SHORT_MAX_TOKENS=128 \
BENCH_LONG_MAX_TOKENS=128 \
BENCH_RETRIES=1 \
python3 benchmark_lmstudio.py
```

输出：
- `benchmark_report.json`
- `benchmark_report.md`

## 6. OpenAPI 协议约定（必须保持兼容）

当前控制面必须兼容这些路径：
- `GET /status`
- `POST /apply`
- `GET /api/v1/status`
- `POST /api/v1/apply`

单独验证：

```bash
bash scripts/stack_verify_openapi.sh
```

## 7. `public/` 上传规范

`public/` 目录仅用于远端上传分发，不等于运行目录。

必须遵守：
- 允许：脚本、配置模板、文档。
- 禁止：日志、缓存、数据库、PID、私钥、密码、Token。
- 禁止提交任何本地临时产物。

## 8. Skill 使用（防遗忘）

本仓提供运维 skill：`skills/rag-stack-ops/SKILL.md`。

用途：
- 每次变更前后，按固定流程执行 `up -> status -> healthcheck -> openapi -> light benchmark`。
- 防止只改代码、不跑全流程。

建议：
- 将该 skill 同步到本机 `$CODEX_HOME/skills/rag-stack-ops/` 后，在 Codex 中可直接触发。

## 9. 常见故障

### 9.1 `stack_healthcheck.sh` 失败

先跑：

```bash
bash scripts/stack_status.sh
```

判断是端口未起还是 OpenAPI 返回异常，再处理。

### 9.2 `stack_verify_openapi.sh` 报缺少路径

说明控制面接口回归不兼容，必须先修复接口再上线。

### 9.3 压测失败但服务可访问

优先降低参数（并发/上下文/token），确认可跑通后再逐步加压。

## 10. 安全原则

- 文档中的账号/口令只能作占位示例，不得写入真实值。
- 所有敏感信息必须走环境变量或外部密管。
- 每次凭据暴露后都应立即轮换（特别是 PAT/SSH 密钥）。

## 11. 后续路线（你已规划）

- 保持当前 Transit-first 基线稳定。
- 后续引入 vLLM 架构并接 LMS。
- 持续沿用这套脚本与 OpenAPI 验收契约，避免迁移回归。
