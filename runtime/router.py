from __future__ import annotations

import json
from typing import Any
from urllib import error as urlerror
from urllib import request

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from runtime.cache import build_exact_cache_key, choose_cache
from runtime.config import RuntimeConfig


def _post_json(url: str, payload: dict[str, Any], timeout: int = 900) -> dict[str, Any]:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _get_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def create_app() -> FastAPI:
    cfg = RuntimeConfig.from_env()
    cache = choose_cache(cfg.redis_url)
    app = FastAPI(title="RAG Runtime Router", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "lmstudio_base_url": cfg.lmstudio_base_url,
            "cache_backend": cache.version(),
            "prompt_version": cfg.prompt_version,
            "retrieval_version": cfg.retrieval_version,
            "profiles": list(cfg.profiles.keys()),
        }

    @app.get("/v1/models")
    def list_models() -> dict[str, Any]:
        upstream = _get_json(f"{cfg.lmstudio_base_url}/models")
        aliases = [{"id": k, "object": "model", "owned_by": "rag-router"} for k in cfg.profiles]
        data = upstream.get("data", []) if isinstance(upstream, dict) else []
        return {"object": "list", "data": aliases + data}

    @app.post("/admin/cache/invalidate")
    async def invalidate_cache(req: Request) -> dict[str, Any]:
        body = await req.json() if req.headers.get("content-type", "").startswith("application/json") else {}
        prefix = body.get("prefix") if isinstance(body, dict) else None
        removed = cache.invalidate(prefix=prefix)
        return {"invalidated": removed, "prefix": prefix}

    @app.post("/v1/chat/completions")
    async def chat_completions(req: Request) -> JSONResponse:
        try:
            payload = await req.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid json body: {exc}")

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload must be object")

        route_hint = payload.get("route")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        if not route_hint:
            route_hint = metadata.get("route_profile")

        profile = cfg.resolve_alias(str(route_hint)) if route_hint else cfg.resolve_request_model(payload.get("model"))

        lm_payload = dict(payload)
        lm_payload["model"] = profile.model_id
        if "max_tokens" not in lm_payload:
            lm_payload["max_tokens"] = profile.max_tokens

        messages = lm_payload.get("messages")
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="messages must be list")

        top_k = int(payload.get("top_k", 20))
        prompt_version = str(payload.get("prompt_version", cfg.prompt_version))
        retrieval_version = str(payload.get("retrieval_version", cfg.retrieval_version))
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        stream = bool(payload.get("stream", False))

        key = build_exact_cache_key(
            model_alias=profile.alias,
            prompt_version=prompt_version,
            retrieval_version=retrieval_version,
            top_k=top_k,
            max_tokens=int(lm_payload.get("max_tokens", profile.max_tokens)),
            messages=messages,
            extra_filters=filters,
        )

        if not stream:
            cached = cache.get(key)
            if cached is not None:
                cached["cache"] = {"hit": True, "backend": cache.version(), "key": key}
                return JSONResponse(cached)

        try:
            result = _post_json(f"{cfg.lmstudio_base_url}/chat/completions", lm_payload)
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=exc.code, detail=detail)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"upstream request failed: {exc}")

        result["route"] = {
            "alias": profile.alias,
            "model_id": profile.model_id,
            "context_length": profile.context_length,
            "parallel": profile.parallel,
            "gpu_binding": profile.gpu_binding,
        }
        result["cache"] = {"hit": False, "backend": cache.version(), "key": key}

        if not stream:
            cache.set(key, result, ttl_seconds=cfg.cache_ttl_seconds)

        return JSONResponse(result)

    return app


app = create_app()
