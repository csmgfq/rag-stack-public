# rag-stack-public

RAG 基础设施第二版汇总仓库（单仓入口，Transit-first 运行）。

本仓库统一三条链路：
- Runtime：LM Studio 路由与缓存（默认主链路）
- vLLM：并行后端（灰度接入，不替换现网）
- ReAct Agent：OpenAI 兼容入口，内部调用检索 + 推理

## 1. 当前策略

- 默认保持现网链路：`LM Studio + monitoring + tailscale proxy`
- 新能力采用并行接入：`vLLM` 与 `ReAct` 都通过显式 route 触发
- 运维入口统一走 `scripts/stack_*.sh`

## 2. 仓库结构

```text
rag-stack-public/
├── README.md
├── benchmark_lmstudio.py
├── runtime/                              # runtime router + launcher
├── react_agent/                          # ReAct OpenAI-compatible service
├── scripts/
│   ├── clean_data.sh                     # 阶段0：清洗语料 -> JSONL
│   ├── build_index.sh                    # 阶段0：构建简易检索索引
│   ├── vllm_smoke.sh                     # 阶段A：vLLM 冒烟
│   ├── react_smoke.sh                    # 阶段B：ReAct 冒烟
│   ├── rollback_check.sh                 # 回滚安全检查
│   ├── stack_up.sh / stack_status.sh / stack_healthcheck.sh / stack_verify_openapi.sh
│   ├── start_single_gpu_runtime.sh
│   └── start_react_agent.sh
├── kb/processed/                         # 清洗 JSONL 与索引输出
├── docs/
│   └── kb_cleaning_preview.md            # raw -> cleaned 示例
├── skills/
│   └── rag-stack-ops/SKILL.md
└── public/                               # 对外上传目录（仅分发内容）
```

## 3. 环境与入口

容器入口：
```bash
ssh -p 50001 root@3090-6.grifcc.top
cd /workspace/rag-stack-public
```

建议先准备环境变量：
```bash
cp scripts/runtime_env.example scripts/runtime_env.sh
source scripts/runtime_env.sh
```

## 4. 阶段0：数据清洗与样例化（JSONL）

输入（默认）：
- `KB_CHAT_EXPORT=/Volumes/192.168.31.34/app/Windows/chat-export-1776788331981.json`
- `KB_MARKDOWN_FILE=/Volumes/192.168.31.34/rag-fnos/source/鱼皮 rag 概念技术解答.md`

执行：
```bash
bash scripts/clean_data.sh
bash scripts/build_index.sh
```

输出：
- `kb/processed/cleaned_kb.jsonl`
- `kb/processed/simple_index.json`
- `docs/kb_cleaning_preview.md`

JSONL 字段契约：
- `doc_id`
- `source_path`
- `source_type`
- `title`
- `chunk_id`
- `text`
- `tags`
- `created_at`

清洗规则：
- 聊天导出：提取用户问题/结论/约束，去空消息、去系统噪声、脱敏（IP/口令/token/账号）
- Markdown 技术文：去图片与 data-uri，按标题切块并保留 tags（`rag_basics`、`rag_variant`、`agentic`）

## 5. 阶段A：vLLM 并行接入（不替换）

先跑现网基线：
```bash
bash scripts/stack_up.sh
bash scripts/stack_status.sh
bash scripts/stack_healthcheck.sh
bash scripts/stack_verify_openapi.sh
```

再跑 vLLM 冒烟：
```bash
bash scripts/vllm_smoke.sh
```

Runtime 路由约定：
- 默认：LM Studio
- 显式 `route=vllm`：走 `VLLM_BASE_URL`
- 显式 `route=react`：走 `REACT_BASE_URL`

## 6. 阶段B：ReAct 接入（OpenAI 兼容）

启动 ReAct：
```bash
bash scripts/start_react_agent.sh
```

冒烟：
```bash
bash scripts/react_smoke.sh
```

ReAct 对外契约：
- `GET /v1/models`
- `POST /v1/chat/completions`
- `GET /health`
- `POST /admin/reload`（重新加载索引）

## 7. 全流程验收顺序

```bash
bash scripts/clean_data.sh
bash scripts/build_index.sh
bash scripts/stack_up.sh
bash scripts/stack_status.sh
bash scripts/stack_healthcheck.sh
bash scripts/stack_verify_openapi.sh
bash scripts/vllm_smoke.sh
bash scripts/react_smoke.sh
bash scripts/rollback_check.sh
```

## 8. 回滚与安全

安全默认停机：
```bash
bash scripts/stack_down.sh
```

强制停历史链路：
```bash
bash scripts/stack_down.sh --force-stop-legacy
```

回滚检查：
```bash
bash scripts/rollback_check.sh
```

## 9. 兼容性要求（必须保持）

tailscale-proxy OpenAPI 保持不变：
- `/status`
- `/apply`
- `/api/v1/status`
- `/api/v1/apply`

## 10. 敏感信息原则

- 仓库禁止提交口令、token、私钥、内网凭据
- `public/` 仅保留可分发内容，不包含本地运行态文件
- 第三方语料仅用于内部检索与示例，不外发原文
