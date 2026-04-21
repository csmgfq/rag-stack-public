---
name: rag-stack-ops
description: Use this skill when operating rag-stack transit-first deployment, including KB cleaning/index build, vLLM smoke, ReAct smoke, OpenAPI compatibility checks, and rollback safety checks.
---

# rag-stack-ops

## When to use

Use this skill when the user asks to:
- 跑 rag-stack 全流程验收（不只改代码）
- 做知识库语料清洗并生成 JSONL 样例
- 做 vLLM 并行链路 smoke
- 做 ReAct OpenAI 兼容链路 smoke
- 做上线前后 rollback 安全检查

Default working directory:
- `/workspace/rag-stack-public`

## Guardrails

- 优先保护现网：除非明确要求，不执行破坏性停服。
- 默认走仓库脚本：`scripts/*.sh`。
- 不在仓库记录敏感信息（password/token/private key/内网凭据）。
- OpenAPI 兼容失败时，先修复接口再继续上线步骤。

## Standard workflow

Run in this order:

1. clean_data
```bash
cd /workspace/rag-stack-public
bash scripts/clean_data.sh
```

2. build_index
```bash
bash scripts/build_index.sh
```

3. stack baseline checks
```bash
bash scripts/stack_up.sh
bash scripts/stack_status.sh
bash scripts/stack_healthcheck.sh
bash scripts/stack_verify_openapi.sh
```

4. vllm_smoke
```bash
bash scripts/vllm_smoke.sh
```

5. react_smoke
```bash
bash scripts/react_smoke.sh
```

6. rollback_check
```bash
bash scripts/rollback_check.sh
```

## Completion criteria

A change is complete only if:
- `clean_data` produced JSONL with non-empty chunks
- `build_index` succeeded and index is readable
- `stack_healthcheck` and `stack_verify_openapi` passed
- `vllm_smoke` and `react_smoke` both passed
- `rollback_check` passed with legacy/transit chain intact
