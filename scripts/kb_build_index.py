#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9_\-\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def build_index(rows: list[dict[str, Any]]) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    posting: dict[str, dict[str, int]] = defaultdict(dict)

    for i, row in enumerate(rows):
        text = str(row.get("text", ""))
        chunk_id = str(row.get("chunk_id", f"chunk_{i}"))
        tokens = tokenize(text)
        if not tokens:
            continue

        chunks.append(
            {
                "chunk_id": chunk_id,
                "doc_id": row.get("doc_id"),
                "title": row.get("title"),
                "source_path": row.get("source_path"),
                "source_type": row.get("source_type"),
                "tags": row.get("tags", []),
                "text": text,
            }
        )

        freqs: dict[str, int] = defaultdict(int)
        for t in tokens:
            freqs[t] += 1
        for t, c in freqs.items():
            posting[t][chunk_id] = c

    return {"version": 1, "chunk_count": len(chunks), "chunks": chunks, "posting": posting}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build simple lexical KB index from cleaned JSONL")
    p.add_argument("--input-jsonl", default="kb/processed/cleaned_kb.jsonl")
    p.add_argument("--output-index", default="kb/processed/simple_index.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.input_jsonl)
    if not in_path.exists():
        raise SystemExit(f"input jsonl not found: {in_path}")

    rows = load_jsonl(in_path)
    index = build_index(rows)

    out = Path(args.output_index)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"KB_INDEX_OK chunks={index['chunk_count']} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
