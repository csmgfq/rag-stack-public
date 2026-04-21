from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def invalidate(self, prefix: str | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def version(self) -> str:
        raise NotImplementedError


class MemoryCache(CacheBackend):
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._data.get(key)
        if row is None:
            return None
        expires_at, value = row
        if expires_at < time.time():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._data[key] = (time.time() + ttl_seconds, value)

    def invalidate(self, prefix: str | None = None) -> int:
        if prefix is None:
            count = len(self._data)
            self._data.clear()
            return count
        keys = [k for k in self._data if k.startswith(prefix)]
        for key in keys:
            self._data.pop(key, None)
        return len(keys)

    def version(self) -> str:
        return "memory"


class RedisCache(CacheBackend):
    def __init__(self, redis_url: str) -> None:
        import redis  # type: ignore

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def get(self, key: str) -> dict[str, Any] | None:
        raw = self._client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._client.setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False))

    def invalidate(self, prefix: str | None = None) -> int:
        pattern = "rag:l1:*" if prefix is None else f"{prefix}*"
        keys = list(self._client.scan_iter(match=pattern))
        if not keys:
            return 0
        self._client.delete(*keys)
        return len(keys)

    def version(self) -> str:
        return "redis"


def choose_cache(redis_url: str | None) -> CacheBackend:
    if not redis_url:
        return MemoryCache()
    try:
        return RedisCache(redis_url)
    except Exception:
        return MemoryCache()


def _normalize_messages(messages: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for message in messages:
        role = str(message.get("role", "user")).strip().lower()
        content = message.get("content", "")
        if isinstance(content, list):
            text = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
        else:
            text = str(content)
        compact = " ".join(text.split()).lower()
        chunks.append(f"{role}:{compact}")
    return "\n".join(chunks)


def build_exact_cache_key(
    *,
    model_alias: str,
    prompt_version: str,
    retrieval_version: str,
    top_k: int,
    max_tokens: int,
    messages: list[dict[str, Any]],
    extra_filters: dict[str, Any] | None,
) -> str:
    payload = {
        "model_alias": model_alias,
        "prompt_version": prompt_version,
        "retrieval_version": retrieval_version,
        "top_k": top_k,
        "max_tokens": max_tokens,
        "messages": _normalize_messages(messages),
        "filters": extra_filters or {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return "rag:l1:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
