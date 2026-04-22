from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import request


@dataclass
class VLLMLaunchSpec:
    model: str
    host: str = "127.0.0.1"
    port: int = 8000
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 8192
    served_model_name: str | None = None
    trust_remote_code: bool = True
    cuda_visible_devices: str | None = None
    extra_args: str = ""


class VLLMManager:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_root = Path(os.environ.get("RAG_PROJECT_ROOT", "/workspace/rag-stack-public"))
        self.pid_file = Path(os.environ.get("VLLM_CONTROL_PID_FILE", str(self.project_root / "run" / "vllm_control.pid")))
        self.spec_file = Path(os.environ.get("VLLM_CONTROL_SPEC_FILE", str(self.project_root / "run" / "vllm_control_spec.json")))
        self.log_file = Path(os.environ.get("VLLM_CONTROL_LOG_FILE", str(self.project_root / "logs" / "vllm_control.log")))
        self.vllm_bin = os.environ.get("VLLM_CONTROL_BIN", "/opt/miniconda/envs/vllm/bin/vllm")

    def _ensure_parent(self) -> None:
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.spec_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _read_pid(self) -> int | None:
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except Exception:
            return None

    def _write_pid(self, pid: int) -> None:
        self._ensure_parent()
        self.pid_file.write_text(str(pid), encoding="utf-8")

    def _clear_pid(self) -> None:
        try:
            self.pid_file.unlink()
        except Exception:
            pass

    def _process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _first_vllm_pid(self) -> int | None:
        try:
            p = subprocess.run(["pgrep", "-f", "vllm serve"], capture_output=True, text=True, timeout=2, check=False)
            for line in (p.stdout or "").splitlines():
                line = line.strip()
                if line.isdigit():
                    return int(line)
        except Exception:
            return None
        return None

    def _all_vllm_pids(self) -> list[int]:
        out: list[int] = []
        try:
            p = subprocess.run(["pgrep", "-f", "vllm serve"], capture_output=True, text=True, timeout=2, check=False)
            for line in (p.stdout or "").splitlines():
                line = line.strip()
                if line.isdigit():
                    out.append(int(line))
        except Exception:
            return []
        return out

    def _load_spec(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.spec_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_spec(self, spec: VLLMLaunchSpec) -> None:
        self._ensure_parent()
        self.spec_file.write_text(json.dumps(asdict(spec), ensure_ascii=False, indent=2), encoding="utf-8")

    def _models_payload(self, timeout: int = 2) -> dict[str, Any] | None:
        try:
            with request.urlopen(f"{self.base_url}/models", timeout=timeout) as resp:
                return json.load(resp)
        except Exception:
            return None

    def _build_cmd(self, spec: VLLMLaunchSpec) -> list[str]:
        cmd = [
            self.vllm_bin,
            "serve",
            spec.model,
            "--host",
            spec.host,
            "--port",
            str(spec.port),
            "--tensor-parallel-size",
            str(spec.tensor_parallel_size),
            "--gpu-memory-utilization",
            str(spec.gpu_memory_utilization),
            "--max-model-len",
            str(spec.max_model_len),
        ]
        if spec.trust_remote_code:
            cmd.append("--trust-remote-code")
        if spec.served_model_name:
            cmd.extend(["--served-model-name", spec.served_model_name])
        if spec.extra_args.strip():
            cmd.extend(shlex.split(spec.extra_args.strip()))
        return cmd

    def status(self) -> dict[str, Any]:
        pid = self._read_pid()
        managed_alive = bool(pid and self._process_alive(pid))
        if not managed_alive:
            pid = self._first_vllm_pid()
        models = self._models_payload(timeout=2)
        endpoint_up = bool(isinstance(models, dict) and isinstance(models.get("data"), list))
        return {
            "managed_pid": self._read_pid(),
            "active_pid": pid,
            "running": bool(pid),
            "endpoint_up": endpoint_up,
            "base_url": self.base_url,
            "models": models.get("data", []) if isinstance(models, dict) else [],
            "last_spec": self._load_spec(),
            "log_file": str(self.log_file),
            "pid_file": str(self.pid_file),
        }

    def load(self, spec: VLLMLaunchSpec, wait_seconds: float = 1.5) -> dict[str, Any]:
        st = self.status()
        if st.get("running"):
            return {"ok": False, "detail": "vllm already running", "status": st}

        cmd = self._build_cmd(spec)
        self._ensure_parent()
        env = os.environ.copy()
        if spec.cuda_visible_devices:
            env["CUDA_VISIBLE_DEVICES"] = spec.cuda_visible_devices

        with self.log_file.open("a", encoding="utf-8") as logf:
            logf.write(f"\n[{time.strftime('%F %T')}] start: {' '.join(cmd)}\n")
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                env=env,
                stdout=logf,
                stderr=logf,
                start_new_session=True,
            )

        self._write_pid(proc.pid)
        self._save_spec(spec)
        time.sleep(max(wait_seconds, 0.0))
        return {"ok": True, "pid": proc.pid, "status": self.status()}

    def unload(self, grace_seconds: float = 8.0) -> dict[str, Any]:
        target_pids = []
        pid = self._read_pid()
        if pid:
            target_pids.append(pid)
        target_pids.extend([p for p in self._all_vllm_pids() if p not in target_pids])

        if not target_pids:
            self._clear_pid()
            return {"ok": True, "detail": "no running vllm process", "status": self.status()}

        for p in target_pids:
            try:
                os.kill(p, signal.SIGTERM)
            except Exception:
                pass

        deadline = time.time() + max(grace_seconds, 1.0)
        while time.time() < deadline:
            alive = [p for p in target_pids if self._process_alive(p)]
            if not alive:
                break
            time.sleep(0.25)

        alive = [p for p in target_pids if self._process_alive(p)]
        for p in alive:
            try:
                os.kill(p, signal.SIGKILL)
            except Exception:
                pass

        self._clear_pid()
        return {"ok": True, "killed_pids": target_pids, "status": self.status()}

