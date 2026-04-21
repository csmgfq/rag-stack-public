# LM Studio Runtime (Single GPU + Alias + Cache)

## What this adds

- Single-GPU LM Studio launch with `CUDA_VISIBLE_DEVICES`.
- Alias-based model routing (`rag-main`, `rag-fallback`, `rag-fast`, `rag-longctx`).
- Pluggable L1 exact cache (`MemoryCache` or `RedisCache`).

## Main files

- `runtime/model_profiles.json`: model runtime config layer.
- `runtime/launcher.py`: starts/uses LM Studio and loads alias models.
- `runtime/router.py`: OpenAI-compatible proxy endpoint with alias routing and cache.
- `runtime/cache.py`: cache interface + memory/redis implementations.

## Start

```bash
cd /home/jiangzhiming/workspace/rag-stack
bash scripts/start_single_gpu_runtime.sh
```

Router default endpoint: `http://0.0.0.0:18000`.

## Optional env vars

- `RAG_MODEL_PROFILE_PATH` (default `runtime/model_profiles.json`)
- `RAG_GPU_BINDING` (default from `rag-main.gpu_binding`)
- `REDIS_URL` (if unset, memory cache is used)
- `RAG_CACHE_TTL_SECONDS` (default `21600`)
- `LMSTUDIO_BASE_URL` (default `http://127.0.0.1:1234/v1`)
