#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from runtime.config import RuntimeConfig


def _run(cmd: list[str], env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, env=env, text=True, capture_output=True, check=check)


def _find_lms() -> str:
    candidates = [
        os.environ.get("LMS_CLI_PATH", ""),
        "/home/jiangzhiming/.lmstudio/bin/lms",
        "lms",
    ]
    for c in candidates:
        if not c:
            continue
        if c == "lms":
            return c
        if Path(c).exists():
            return c
    return "lms"


def _server_running(lms_cli: str) -> bool:
    p = _run([lms_cli, "server", "status"], check=False)
    text = (p.stdout + p.stderr).lower()
    return p.returncode == 0 and "running" in text


def _ensure_server(lms_cli: str, host: str, port: int, env: dict[str, str]) -> None:
    if _server_running(lms_cli):
        return
    _run([lms_cli, "server", "start", "--bind", host, "--port", str(port)], env=env, check=True)


def _load_alias(lms_cli: str, cfg: RuntimeConfig, alias: str, env: dict[str, str]) -> None:
    p = cfg.resolve_alias(alias)
    cmd = [
        lms_cli,
        "load",
        p.model_id,
        "--identifier",
        alias,
        "--gpu",
        "max",
        "--context-length",
        str(p.context_length),
        "--parallel",
        str(p.parallel),
        "--yes",
    ]
    _run(cmd, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch LM Studio with single GPU binding and alias loading")
    parser.add_argument("--host", default=os.environ.get("LMS_SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("LMS_SERVER_PORT", "1234")))
    parser.add_argument("--profile-path", default=os.environ.get("RAG_MODEL_PROFILE_PATH", "runtime/model_profiles.json"))
    parser.add_argument("--main-alias", default=os.environ.get("RAG_MAIN_ALIAS", "rag-main"))
    parser.add_argument("--fallback-alias", default=os.environ.get("RAG_FALLBACK_ALIAS", "rag-fallback"))
    parser.add_argument("--gpu-binding", default=os.environ.get("RAG_GPU_BINDING"))
    args = parser.parse_args()

    os.environ["RAG_MODEL_PROFILE_PATH"] = args.profile_path
    cfg = RuntimeConfig.from_env()
    lms_cli = _find_lms()

    main_profile = cfg.resolve_alias(args.main_alias)
    gpu_binding = args.gpu_binding or main_profile.gpu_binding

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu_binding

    _ensure_server(lms_cli, args.host, args.port, env)
    _load_alias(lms_cli, cfg, args.main_alias, env)
    if args.fallback_alias in cfg.profiles and args.fallback_alias != args.main_alias:
        _load_alias(lms_cli, cfg, args.fallback_alias, env)

    print(
        "LM Studio ready:",
        f"host={args.host}",
        f"port={args.port}",
        f"main_alias={args.main_alias}",
        f"fallback_alias={args.fallback_alias}",
        f"cuda_visible_devices={gpu_binding}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
