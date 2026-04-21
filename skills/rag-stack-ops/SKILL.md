---
name: rag-stack-ops
description: Use this skill when operating or validating the rag-stack transit-first deployment, including startup, status checks, OpenAPI compatibility checks, and light LMStudio benchmark smoke tests.
---

# rag-stack-ops

## When to use

Use this skill when the user asks to:
- 启动/停止/检查 rag-stack 监看链路
- 验证 OpenAPI `/status` `/apply` 兼容性
- 做“可跑通”级别 LMStudio 轻量压测
- 做改动后的全流程验收（而不是只改文件）

Default working directory:
- `/workspace/rag-stack-public`

## Guardrails

- 优先保护现网：除非明确要求，不执行破坏性停服。
- 默认使用仓库脚本，不手搓替代命令。
- 不在仓库记录敏感信息（密码、token、私钥、内网凭据）。
- 若接口不兼容，先修复再继续后续步骤。

## Standard workflow

Run in this order:

1. Start stack
```bash
cd /workspace/rag-stack-public
bash scripts/stack_up.sh
```

2. Check process/ports
```bash
bash scripts/stack_status.sh
```

3. Healthcheck
```bash
bash scripts/stack_healthcheck.sh
```

4. OpenAPI compatibility
```bash
bash scripts/stack_verify_openapi.sh
```

5. Light benchmark smoke test
```bash
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

## Runtime single-GPU checklist

1. Prepare env
```bash
cp scripts/runtime_env.example scripts/runtime_env.sh
```

2. Verify key values in `scripts/runtime_env.sh`
- `LMSTUDIO_BASE_URL`
- `RAG_GPU_BINDING=0` (or target card)
- `RAG_ROUTER_PORT`

3. Start runtime
```bash
bash scripts/start_single_gpu_runtime.sh
```

## Failure handling

- `stack_healthcheck` fails:
  - run `stack_status` first, determine whether port failure or OpenAPI failure.
- OpenAPI path missing:
  - restore compatibility for `/status` `/apply` and `/api/v1/*` aliases.
- benchmark unstable:
  - reduce concurrency/context first; keep smoke-test goal as baseline.

## Completion criteria

A change is considered complete only if:
- `stack_status` shows expected ports and processes
- `stack_healthcheck` passes
- `stack_verify_openapi` passes
- light benchmark completes and outputs reports
