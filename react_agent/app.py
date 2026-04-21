from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request

from fastapi import FastAPI, HTTPException, Request


@dataclass
class KBChunk:
    chunk_id: str
    title: str
    source_path: str
    text: str
    tags: list[str]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "chunk_count": 0, "chunks": [], "posting": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    token = []
    for ch in text.lower():
        if ch.isalnum() or ch == "_" or "\u4e00" <= ch <= "\u9fff":
            token.append(ch)
        else:
            if token:
                out.append("".join(token))
            token = []
    if token:
        out.append("".join(token))
    return out


class SimpleRetriever:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.reload()

    def reload(self) -> None:
        data = _load_json(self.index_path)
        self.chunks: dict[str, KBChunk] = {}
        for row in data.get("chunks", []):
            cid = str(row.get("chunk_id", ""))
            if not cid:
                continue
            self.chunks[cid] = KBChunk(
                chunk_id=cid,
                title=str(row.get("title", "Untitled")),
                source_path=str(row.get("source_path", "")),
                text=str(row.get("text", "")),
                tags=[str(x) for x in row.get("tags", [])],
            )
        self.posting: dict[str, dict[str, int]] = {
            str(t): {str(k): int(v) for k, v in posting.items()}
            for t, posting in data.get("posting", {}).items()
            if isinstance(posting, dict)
        }

    def search(self, query: str, k: int = 4) -> list[KBChunk]:
        scores: dict[str, int] = {}
        for token in _tokens(query):
            posting = self.posting.get(token, {})
            for cid, freq in posting.items():
                scores[cid] = scores.get(cid, 0) + freq

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        out: list[KBChunk] = []
        for cid, _ in ranked[:k]:
            chunk = self.chunks.get(cid)
            if chunk:
                out.append(chunk)
        return out


def _call_openai_chat(base_url: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    req = request.Request(
        f"{base_url.rstrip('''/''')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_user_query(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if str(msg.get("role")) == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
    return ""


def create_app() -> FastAPI:
    app = FastAPI(title="ReAct Agent (OpenAI Compatible)", version="0.1.0")

    index_path = Path(os.environ.get("RAG_KB_INDEX_PATH", "kb/processed/simple_index.json"))
    retriever = SimpleRetriever(index_path)
    llm_base = os.environ.get("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
    fallback_base = os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    default_model = os.environ.get("REACT_DEFAULT_MODEL", "google/gemma-4-e4b")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "index_path": str(index_path),
            "chunk_count": len(retriever.chunks),
            "llm_base": llm_base,
            "fallback_base": fallback_base,
        }

    @app.get("/v1/models")
    def models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": "react-agent", "object": "model", "owned_by": "rag-stack"}]}

    @app.post("/admin/reload")
    def reload_index() -> dict[str, Any]:
        retriever.reload()
        return {"reloaded": True, "chunk_count": len(retriever.chunks)}

    @app.post("/v1/chat/completions")
    async def chat(req: Request) -> dict[str, Any]:
        try:
            payload = await req.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid json body: {exc}")

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload must be object")

        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="messages must be list")

        query = _extract_user_query(messages)
        refs = retriever.search(query, k=int(payload.get("top_k", 4)))

        reference_blocks = []
        for i, ref in enumerate(refs, 1):
            reference_blocks.append(
                f"[{i}] title={ref.title} source={ref.source_path}\n{ref.text[:800]}"
            )

        system_prompt = (
            "你是RAG ReAct代理。请优先依据参考资料回答。"
            "如果参考资料不足，明确说明‘资料不足’，再给出保守建议。"
            "回答末尾附上引用编号。"
        )

        upstream_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if reference_blocks:
            upstream_messages.append({"role": "system", "content": "参考资料:\n" + "\n\n".join(reference_blocks)})
        upstream_messages.extend(messages)

        upstream_payload = {
            "model": payload.get("model") or default_model,
            "messages": upstream_messages,
            "temperature": payload.get("temperature", 0.2),
            "max_tokens": payload.get("max_tokens", 512),
            "stream": False,
        }

        used_backend = "vllm"
        try:
            result = _call_openai_chat(llm_base, upstream_payload)
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=exc.code, detail=detail)
        except Exception:
            used_backend = "lmstudio-fallback"
            try:
                result = _call_openai_chat(fallback_base, upstream_payload)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"react upstream failed: {exc}")

        choices = result.get("choices") if isinstance(result, dict) else None
        if not isinstance(choices, list) or not choices:
            raise HTTPException(status_code=502, detail="invalid upstream completion response")

        now = int(time.time())
        out = {
            "id": f"chatcmpl-react-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": now,
            "model": "react-agent",
            "choices": choices,
            "usage": result.get("usage", {}),
            "route": {
                "backend": used_backend,
                "retrieved_chunks": [r.chunk_id for r in refs],
                "retrieved_count": len(refs),
            },
        }
        return out

    return app


app = create_app()
