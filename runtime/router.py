from __future__ import annotations

import json
import os
from typing import Any
from urllib import error as urlerror
from urllib import request

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from runtime.cache import build_exact_cache_key, choose_cache
from runtime.config import RuntimeConfig
from runtime.vllm_manager import VLLMLaunchSpec, VLLMManager


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


def _safe_get_json(url: str, timeout: int = 3) -> dict[str, Any] | None:
    try:
        return _get_json(url, timeout=timeout)
    except Exception:
        return None


VLLM_PARAM_KEYS = {
    "temperature",
    "top_p",
    "top_k",
    "max_tokens",
    "presence_penalty",
    "frequency_penalty",
    "repetition_penalty",
    "min_p",
}


class VLLMParamsUpdate(BaseModel):
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    repetition_penalty: float | None = None
    min_p: float | None = None
    reset: bool = False


class VLLMLoadRequest(BaseModel):
    model: str
    host: str = "127.0.0.1"
    port: int = 8000
    tensor_parallel_size: int = Field(default=1, ge=1)
    gpu_memory_utilization: float = Field(default=0.9, gt=0.0, le=0.99)
    max_model_len: int = Field(default=8192, ge=512)
    served_model_name: str | None = None
    trust_remote_code: bool = True
    cuda_visible_devices: str | None = None
    extra_args: str = ""


def create_app() -> FastAPI:
    cfg = RuntimeConfig.from_env()
    cache = choose_cache(cfg.redis_url)
    app = FastAPI(title="RAG Runtime Router", version="0.3.0")

    vllm_manager = VLLMManager(cfg.vllm_base_url or "http://127.0.0.1:8000/v1")
    vllm_defaults: dict[str, Any] = {}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "lmstudio_base_url": cfg.lmstudio_base_url,
            "vllm_base_url": cfg.vllm_base_url,
            "react_base_url": cfg.react_base_url,
            "cache_backend": cache.version(),
            "prompt_version": cfg.prompt_version,
            "retrieval_version": cfg.retrieval_version,
            "profiles": list(cfg.profiles.keys()),
            "supported_routes": ["lmstudio", "vllm", "react"],
            "vllm_control": vllm_manager.status(),
            "vllm_generation_defaults": vllm_defaults,
        }

    @app.get("/v1/models")
    def list_models() -> dict[str, Any]:
        aliases = [{"id": k, "object": "model", "owned_by": "rag-router"} for k in cfg.profiles]
        aliases.extend(
            [
                {"id": "route:vllm", "object": "model", "owned_by": "rag-router"},
                {"id": "route:react", "object": "model", "owned_by": "rag-router"},
            ]
        )

        upstream: list[dict[str, Any]] = []
        for base in [cfg.lmstudio_base_url, cfg.vllm_base_url, cfg.react_base_url]:
            if not base:
                continue
            data = _safe_get_json(f"{base}/models")
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                for item in data["data"]:
                    if isinstance(item, dict):
                        upstream.append(item)

        return {"object": "list", "data": aliases + upstream}

    @app.post("/admin/cache/invalidate")
    async def invalidate_cache(req: Request) -> dict[str, Any]:
        body = await req.json() if req.headers.get("content-type", "").startswith("application/json") else {}
        prefix = body.get("prefix") if isinstance(body, dict) else None
        removed = cache.invalidate(prefix=prefix)
        return {"invalidated": removed, "prefix": prefix}

    @app.get("/admin/v1/vllm/status")
    def admin_vllm_status() -> dict[str, Any]:
        return vllm_manager.status()

    @app.post("/admin/v1/vllm/load")
    def admin_vllm_load(req: VLLMLoadRequest) -> dict[str, Any]:
        spec = VLLMLaunchSpec(
            model=req.model,
            host=req.host,
            port=req.port,
            tensor_parallel_size=req.tensor_parallel_size,
            gpu_memory_utilization=req.gpu_memory_utilization,
            max_model_len=req.max_model_len,
            served_model_name=req.served_model_name,
            trust_remote_code=req.trust_remote_code,
            cuda_visible_devices=req.cuda_visible_devices,
            extra_args=req.extra_args,
        )
        result = vllm_manager.load(spec)
        if not result.get("ok"):
            raise HTTPException(status_code=409, detail=result)
        return result

    @app.post("/admin/v1/vllm/unload")
    def admin_vllm_unload() -> dict[str, Any]:
        return vllm_manager.unload()

    @app.get("/admin/v1/vllm/params")
    def admin_vllm_params_get() -> dict[str, Any]:
        return {"defaults": vllm_defaults}

    @app.post("/admin/v1/vllm/params")
    def admin_vllm_params_set(req: VLLMParamsUpdate) -> dict[str, Any]:
        nonlocal vllm_defaults
        payload = req.model_dump()
        reset = bool(payload.pop("reset", False))
        updates = {k: v for k, v in payload.items() if k in VLLM_PARAM_KEYS and v is not None}
        if reset:
            vllm_defaults = updates
        else:
            merged = dict(vllm_defaults)
            merged.update(updates)
            vllm_defaults = merged
        return {"defaults": vllm_defaults}

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
        if not route_hint:
            route_hint = metadata.get("route")

        try:
            backend, base_url = cfg.upstream_for_route(str(route_hint) if route_hint else None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        profile = cfg.resolve_alias(str(route_hint)) if route_hint in cfg.profiles else cfg.resolve_request_model(payload.get("model"))

        lm_payload = dict(payload)
        lm_payload.pop("route", None)
        if isinstance(lm_payload.get("metadata"), dict):
            lm_payload["metadata"] = dict(lm_payload["metadata"])
            lm_payload["metadata"].pop("route", None)
            lm_payload["metadata"].pop("route_profile", None)

        if backend == "vllm":
            requested = payload.get("model")
            if isinstance(requested, str) and requested.strip():
                lm_payload["model"] = requested.strip()
            else:
                lm_payload["model"] = profile.model_id
            for k, v in vllm_defaults.items():
                lm_payload.setdefault(k, v)
        elif backend != "react":
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

        model_for_key = str(lm_payload.get("model", profile.model_id))
        key = build_exact_cache_key(
            model_alias=f"{backend}:{model_for_key}",
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
            result = _post_json(f"{base_url}/chat/completions", lm_payload)
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=exc.code, detail=detail)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"upstream request failed: {exc}")

        result["route"] = {
            "backend": backend,
            "base_url": base_url,
            "alias": profile.alias,
            "model_id": str(lm_payload.get("model", profile.model_id)),
            "context_length": profile.context_length,
            "parallel": profile.parallel,
            "gpu_binding": profile.gpu_binding,
            "vllm_defaults": vllm_defaults if backend == "vllm" else {},
        }
        result["cache"] = {"hit": False, "backend": cache.version(), "key": key}

        if not stream:
            cache.set(key, result, ttl_seconds=cfg.cache_ttl_seconds)

        return JSONResponse(result)

    return app


app = create_app()

