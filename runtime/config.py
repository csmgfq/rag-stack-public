from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelProfile:
    alias: str
    model_id: str
    context_length: int
    parallel: int
    gpu_binding: str
    max_tokens: int


class RuntimeConfig:
    def __init__(
        self,
        *,
        lmstudio_base_url: str,
        profile_path: Path,
        prompt_version: str,
        retrieval_version: str,
        redis_url: str | None,
        cache_ttl_seconds: int,
        allow_raw_model_id: bool,
    ) -> None:
        self.lmstudio_base_url = lmstudio_base_url.rstrip("/")
        self.profile_path = profile_path
        self.prompt_version = prompt_version
        self.retrieval_version = retrieval_version
        self.redis_url = redis_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self.allow_raw_model_id = allow_raw_model_id

        data = self._load_profile_file(profile_path)
        self.route_order = [str(alias) for alias in data.get("route_order", [])]
        self.profiles = self._parse_profiles(data.get("profiles", {}))
        if "rag-main" not in self.profiles:
            raise ValueError("model_profiles.json must define rag-main")

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        profile_path = Path(os.environ.get("RAG_MODEL_PROFILE_PATH", "runtime/model_profiles.json"))
        return cls(
            lmstudio_base_url=os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
            profile_path=profile_path,
            prompt_version=os.environ.get("RAG_PROMPT_VERSION", "v1"),
            retrieval_version=os.environ.get("RAG_RETRIEVAL_VERSION", "v1"),
            redis_url=os.environ.get("REDIS_URL"),
            cache_ttl_seconds=int(os.environ.get("RAG_CACHE_TTL_SECONDS", "21600")),
            allow_raw_model_id=os.environ.get("RAG_ALLOW_RAW_MODEL_ID", "false").lower() == "true",
        )

    @staticmethod
    def _load_profile_file(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Profile file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Profile file must be a JSON object")
        return data

    @staticmethod
    def _parse_profiles(raw: dict[str, Any]) -> dict[str, ModelProfile]:
        parsed: dict[str, ModelProfile] = {}
        for alias, value in raw.items():
            if not isinstance(value, dict):
                raise ValueError(f"Invalid profile for alias: {alias}")
            parsed[alias] = ModelProfile(
                alias=alias,
                model_id=str(value["model_id"]),
                context_length=int(value["context_length"]),
                parallel=int(value["parallel"]),
                gpu_binding=str(value["gpu_binding"]),
                max_tokens=int(value.get("max_tokens", 1024)),
            )
        return parsed

    def resolve_alias(self, alias: str | None) -> ModelProfile:
        key = alias or "rag-main"
        return self.profiles.get(key, self.profiles["rag-main"])

    def resolve_request_model(self, model: str | None) -> ModelProfile:
        if not model:
            return self.profiles["rag-main"]
        if model in self.profiles:
            return self.profiles[model]
        if self.allow_raw_model_id:
            base = self.profiles["rag-main"]
            return ModelProfile(
                alias="raw-model",
                model_id=model,
                context_length=base.context_length,
                parallel=base.parallel,
                gpu_binding=base.gpu_binding,
                max_tokens=base.max_tokens,
            )
        return self.profiles["rag-main"]
