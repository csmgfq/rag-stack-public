# Runtime Router (LM Studio + vLLM + ReAct)

## Capabilities

- Single-GPU LM Studio launch with `CUDA_VISIBLE_DEVICES`.
- Alias-based model routing (`rag-main`, `rag-fallback`, ...).
- Pluggable exact cache (`MemoryCache` or `RedisCache`).
- Multi-backend route selection:
  - default -> LM Studio
  - `route=vllm` -> vLLM backend
  - `route=react` -> ReAct backend

## Main files

- `runtime/model_profiles.json`: model profile config.
- `runtime/launcher.py`: starts/uses LM Studio and loads aliases.
- `runtime/router.py`: OpenAI-compatible proxy endpoint with cache and backend routing.
- `runtime/config.py`: env + profile loading + backend selection.

## Start

```bash
cd /workspace/rag-stack-public
bash scripts/start_single_gpu_runtime.sh
```

Router default endpoint: `http://0.0.0.0:18000`.

## Key env vars

- `LMSTUDIO_BASE_URL` (default `http://127.0.0.1:1234/v1`)
- `VLLM_BASE_URL` (default `http://127.0.0.1:8000/v1`)
- `REACT_BASE_URL` (default `http://127.0.0.1:18001/v1`)
- `RAG_MODEL_PROFILE_PATH` (default `runtime/model_profiles.json`)
- `RAG_GPU_BINDING` (default from `rag-main.gpu_binding`)
- `REDIS_URL` (if unset, memory cache is used)
- `RAG_CACHE_TTL_SECONDS` (default `21600`)
