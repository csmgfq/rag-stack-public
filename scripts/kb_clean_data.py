#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any

IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\([^\)]*\)")
DATA_URI_RE = re.compile(r"data:image/[^\s\)]*")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PASSWORD_RE = re.compile(r"(?i)(password|passwd|口令|密码)\s*[:：=]\s*[^\s,，;；]+")
TOKEN_RE = re.compile(r"\b(?:ghp|sk)-[A-Za-z0-9_\-]{20,}\b")
ACCOUNT_RE = re.compile(r"(?i)(账号|账户|account)\s*[:：=]\s*[A-Za-z0-9_\-@.]{2,}")
WS_RE = re.compile(r"[ \t]+")


def clean_text(text: str) -> str:
    text = IMAGE_MD_RE.sub("", text)
    text = DATA_URI_RE.sub("[REDACTED_DATA_URI]", text)
    text = IPV4_RE.sub("[REDACTED_IP]", text)
    text = PASSWORD_RE.sub(r"\1=[REDACTED]", text)
    text = TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = ACCOUNT_RE.sub(r"\1=[REDACTED]", text)
    text = WS_RE.sub(" ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join([ln for ln in lines if ln]).strip()


def stable_doc_id(source_path: str, source_type: str) -> str:
    raw = f"{source_type}:{source_path}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def stable_chunk_id(doc_id: str, title: str, index: int, text: str) -> str:
    raw = f"{doc_id}:{title}:{index}:{text[:80]}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def section_tags(title: str, text: str) -> list[str]:
    body = f"{title}\n{text}".lower()
    tags: list[str] = []
    if "什么是 rag" in body or "naive rag" in body:
        tags.append("rag_basics")
    if "multi-query" in body or "hyde" in body or "变体" in body:
        tags.append("rag_variant")
    if "agentic" in body or "agent" in body or "react" in body:
        tags.append("agentic")
    if "监看" in body or "grafana" in body or "prometheus" in body:
        tags.append("ops")
    if not tags:
        tags.append("reference")
    return sorted(set(tags))


def split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = "Untitled"
    current_lines: list[str] = []

    for line in markdown.splitlines():
        if line.startswith("#"):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line.lstrip("#").strip() or "Untitled"
            current_lines = []
            continue
        current_lines.append(line)

    if current_lines:
        sections.append((current_title, current_lines))

    out: list[tuple[str, str]] = []
    for title, lines in sections:
        text = clean_text("\n".join(lines))
        if text:
            out.append((title, text))
    return out


def split_long_text(text: str, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def extract_chat_records(path: Path, created_at: str) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    doc_id = stable_doc_id(str(path), "chat_export")

    records: list[dict[str, Any]] = []
    if isinstance(raw, list) and raw:
        node = raw[0]
        chat = node.get("chat", {}) if isinstance(node, dict) else {}
        history = chat.get("history", {}) if isinstance(chat, dict) else {}
        messages = history.get("messages", {}) if isinstance(history, dict) else {}
        if isinstance(messages, dict):
            records = [m for m in messages.values() if isinstance(m, dict)]
        else:
            records = [m for m in chat.get("messages", []) if isinstance(m, dict)]

    records = sorted(records, key=lambda m: int(m.get("timestamp") or 0))

    keep_phrases = ["最终", "方案", "总结", "行动", "约束", "不能", "必须", "并行", "react", "vllm", "docker", "tailscale", "socat"]

    idx = 0
    for msg in records:
        role = str(msg.get("role", ""))
        if role not in {"user", "assistant"}:
            continue

        text_blocks: list[str] = []
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            text_blocks.append(content)

        content_list = msg.get("content_list")
        if isinstance(content_list, list):
            for item in content_list:
                if isinstance(item, dict):
                    c = item.get("content")
                    if isinstance(c, str) and c.strip():
                        text_blocks.append(c)

        text = clean_text("\n".join(text_blocks))
        if not text:
            continue

        lowered = text.lower()
        if role == "assistant" and not any(p in lowered for p in keep_phrases):
            continue

        title = "chat_user_question" if role == "user" else "chat_assistant_conclusion"
        for part in split_long_text(text):
            chunk_id = stable_chunk_id(doc_id, title, idx, part)
            rows.append(
                {
                    "doc_id": doc_id,
                    "source_path": str(path),
                    "source_type": "chat_export",
                    "title": title,
                    "chunk_id": chunk_id,
                    "text": part,
                    "tags": sorted(set(section_tags(title, part) + [role, "chat"])),
                    "created_at": created_at,
                }
            )
            idx += 1

    return rows


def extract_markdown_records(path: Path, created_at: str) -> list[dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    sections = split_markdown_sections(source)
    doc_id = stable_doc_id(str(path), "markdown")
    rows: list[dict[str, Any]] = []
    idx = 0
    for title, text in sections:
        for part in split_long_text(text):
            chunk_id = stable_chunk_id(doc_id, title, idx, part)
            rows.append(
                {
                    "doc_id": doc_id,
                    "source_path": str(path),
                    "source_type": "markdown",
                    "title": title,
                    "chunk_id": chunk_id,
                    "text": part,
                    "tags": sorted(set(section_tags(title, part) + ["reference"])),
                    "created_at": created_at,
                }
            )
            idx += 1
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_preview(path: Path, rows: list[dict[str, Any]]) -> None:
    sample = rows[:6]
    lines = ["# KB Cleaning Preview", "", "Raw -> Cleaned sample (first 6 chunks)", ""]
    for i, row in enumerate(sample, 1):
        lines.append(f"## Sample {i}")
        lines.append(f"- source: `{row['source_path']}`")
        lines.append(f"- title: `{row['title']}`")
        lines.append(f"- tags: `{', '.join(row['tags'])}`")
        lines.append("")
        lines.append("```text")
        lines.append(row["text"][:600])
        lines.append("```")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean raw chat/markdown files into KB-ready JSONL")
    parser.add_argument("--chat-export", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--out-jsonl", default="kb/processed/cleaned_kb.jsonl")
    parser.add_argument("--out-preview", default="docs/kb_cleaning_preview.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    created_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    chat_path = Path(args.chat_export)
    md_path = Path(args.markdown)
    if not chat_path.exists():
        raise SystemExit(f"chat export not found: {chat_path}")
    if not md_path.exists():
        raise SystemExit(f"markdown not found: {md_path}")

    rows = extract_chat_records(chat_path, created_at) + extract_markdown_records(md_path, created_at)
    rows = [r for r in rows if r.get("text")]

    out_jsonl = Path(args.out_jsonl)
    write_jsonl(out_jsonl, rows)
    write_preview(Path(args.out_preview), rows)

    print(f"KB_CLEAN_OK rows={len(rows)} out={out_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
