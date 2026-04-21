#!/usr/bin/env python3
import json
import os
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("LM_EXPORTER_PORT", "9401"))
HOST = os.environ.get("LM_EXPORTER_HOST", "127.0.0.1")
LM_URL = os.environ.get("LM_URL", "http://127.0.0.1:1234/v1/models")
ACCESS_TOKEN = os.environ.get("LM_EXPORTER_TOKEN", "").strip()
DEFAULT_BENCHMARK_METRICS_FILE = Path(__file__).resolve().parent / "data" / "benchmark_metrics.json"
BENCHMARK_METRICS_FILE = Path(
    os.environ.get(
        "RAG_BENCHMARK_METRICS_FILE",
        str(DEFAULT_BENCHMARK_METRICS_FILE),
    )
)


def read_meminfo():
    out = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                out[k.strip()] = int(v.strip().split()[0]) * 1024
    except Exception:
        return 0, 0
    total = out.get("MemTotal", 0)
    avail = out.get("MemAvailable", 0)
    used = max(total - avail, 0)
    return total, used


def _candidate_lm_urls():
    candidates: list[str] = []
    seen = set()

    def add(url: str):
        url = (url or "").strip()
        if not url or url in seen:
            return
        seen.add(url)
        candidates.append(url)

    # 1) Explicit env first
    add(LM_URL)

    # 2) Optional fallback env
    add(os.environ.get("LM_URL_FALLBACK", ""))

    # 3) Stable defaults
    add("http://127.0.0.1:1234/v1/models")
    add("http://127.0.0.1:1234/api/v0/models")

    # 4) Read lmstudio configured port when available
    cfg = Path.home() / ".lmstudio" / ".internal" / "http-server-config.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        port = int(data.get("port", 1234))
        host = str(data.get("networkInterface", "127.0.0.1")).strip() or "127.0.0.1"
        if host == "0.0.0.0":
            host = "127.0.0.1"
        add(f"http://{host}:{port}/v1/models")
        add(f"http://{host}:{port}/api/v0/models")
    except Exception:
        pass

    return candidates


def lmstudio_up():
    for url in _candidate_lm_urls():
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.load(resp)
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                return 1
        except Exception:
            continue
    return 0


def process_count(name):
    try:
        r = subprocess.run(["pgrep", "-fc", name], capture_output=True, text=True, check=False)
        return int((r.stdout or "0").strip() or "0")
    except Exception:
        return 0


def gpu_metrics():
    metrics = []
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode != 0:
            return metrics
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 6:
                continue
            gpu = parts[0]
            util = float(parts[1])
            mem_used = float(parts[2])
            mem_total = float(parts[3])
            temp = float(parts[4])
            power = float(parts[5]) if parts[5] not in {"N/A", ""} else 0.0
            metrics.append((gpu, util, mem_used, mem_total, temp, power))
    except Exception:
        return []
    return metrics


def prom_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = []
    for key, value in labels.items():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'{key}="{escaped}"')
    return "{" + ",".join(parts) + "}"


def add_metric(lines: list[str], name: str, value, labels: dict[str, str] | None = None):
    if value is None:
        return
    if isinstance(value, bool):
        value = 1 if value else 0
    lines.append(f"{name}{prom_labels(labels or {})} {value}")


def read_benchmark_metrics():
    try:
        return json.loads(BENCHMARK_METRICS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def append_benchmark_metrics(lines: list[str]):
    payload = read_benchmark_metrics()
    lines.extend(
        [
            "# HELP rag_benchmark_metrics_file_exists Whether benchmark metrics file exists",
            "# TYPE rag_benchmark_metrics_file_exists gauge",
            f"rag_benchmark_metrics_file_exists {1 if BENCHMARK_METRICS_FILE.exists() else 0}",
        ]
    )
    if not payload:
        return

    timestamp = payload.get("timestamp")
    models_total = payload.get("models_total")
    long_context_target_chars = payload.get("long_context_target_chars")
    lines.extend(
        [
            "# HELP rag_benchmark_last_run_timestamp_seconds Unix timestamp of latest benchmark run",
            "# TYPE rag_benchmark_last_run_timestamp_seconds gauge",
        ]
    )
    add_metric(lines, "rag_benchmark_last_run_timestamp_seconds", timestamp)
    lines.extend(
        [
            "# HELP rag_benchmark_models_total Number of benchmarked models",
            "# TYPE rag_benchmark_models_total gauge",
        ]
    )
    add_metric(lines, "rag_benchmark_models_total", models_total)
    lines.extend(
        [
            "# HELP rag_benchmark_long_context_target_chars Target chars used to build long-context prompt",
            "# TYPE rag_benchmark_long_context_target_chars gauge",
        ]
    )
    add_metric(lines, "rag_benchmark_long_context_target_chars", long_context_target_chars)

    metric_defs = {
        "concurrency": "rag_benchmark_concurrency",
        "requests_total": "rag_benchmark_requests_total",
        "requests_ok": "rag_benchmark_requests_ok_total",
        "requests_fail": "rag_benchmark_requests_fail_total",
        "success_rate_pct": "rag_benchmark_success_rate_percent",
        "wall_time_s": "rag_benchmark_wall_time_seconds",
        "requests_per_second": "rag_benchmark_requests_per_second",
        "prompt_chars_avg": "rag_benchmark_prompt_chars_avg",
        "latency_avg_s": "rag_benchmark_latency_avg_seconds",
        "latency_p95_s": "rag_benchmark_latency_p95_seconds",
        "latency_max_s": "rag_benchmark_latency_max_seconds",
        "prompt_tokens_avg": "rag_benchmark_prompt_tokens_avg",
        "prompt_tokens_total": "rag_benchmark_prompt_tokens_total",
        "completion_tokens_avg": "rag_benchmark_completion_tokens_avg",
        "completion_tokens_total": "rag_benchmark_completion_tokens_total",
        "total_tokens_avg": "rag_benchmark_total_tokens_avg",
        "total_tokens_total": "rag_benchmark_total_tokens_total",
        "output_tokens_per_second_avg": "rag_benchmark_output_tokens_per_second_avg",
        "output_tokens_per_second_cluster": "rag_benchmark_output_tokens_per_second_cluster",
    }

    for metric_name in set(metric_defs.values()):
        lines.append(f"# TYPE {metric_name} gauge")

    for scenario_metric in payload.get("scenario_metrics", []):
        labels = {
            "model": str(scenario_metric.get("model", "")),
            "scenario": str(scenario_metric.get("scenario", "")),
        }
        for key, metric_name in metric_defs.items():
            add_metric(lines, metric_name, scenario_metric.get("metrics", {}).get(key), labels)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path not in {"/metrics", "/"}:
            self.send_response(404)
            self.end_headers()
            return

        if ACCESS_TOKEN:
            qs = parse_qs(parsed.query)
            token_query = qs.get("token", [""])[0]
            token_header = self.headers.get("X-Metrics-Token", "")
            auth_header = self.headers.get("Authorization", "")
            token_bearer = ""
            if auth_header.startswith("Bearer "):
                token_bearer = auth_header[7:]
            if token_query != ACCESS_TOKEN and token_header != ACCESS_TOKEN and token_bearer != ACCESS_TOKEN:
                self.send_response(401)
                self.end_headers()
                return

        mem_total, mem_used = read_meminfo()
        ts = int(time.time())
        lines = [
            "# HELP lmstudio_up LM Studio API health (1 up, 0 down)",
            "# TYPE lmstudio_up gauge",
            f"lmstudio_up {lmstudio_up()}",
            "# HELP llmster_process_count Number of llmster processes",
            "# TYPE llmster_process_count gauge",
            f"llmster_process_count {process_count('llmster')}",
            "# HELP lms_process_count Number of lms processes",
            "# TYPE lms_process_count gauge",
            f"lms_process_count {process_count('lms')}",
            "# HELP host_memory_total_bytes Host total memory",
            "# TYPE host_memory_total_bytes gauge",
            f"host_memory_total_bytes {mem_total}",
            "# HELP host_memory_used_bytes Host used memory",
            "# TYPE host_memory_used_bytes gauge",
            f"host_memory_used_bytes {mem_used}",
            "# HELP exporter_unix_time Unix timestamp",
            "# TYPE exporter_unix_time gauge",
            f"exporter_unix_time {ts}",
        ]

        for gpu, util, mem_used_mib, mem_total_mib, temp, power in gpu_metrics():
            lines.append(f"rag_gpu_utilization_percent{{gpu=\"{gpu}\"}} {util}")
            lines.append(f"rag_gpu_memory_used_mib{{gpu=\"{gpu}\"}} {mem_used_mib}")
            lines.append(f"rag_gpu_memory_total_mib{{gpu=\"{gpu}\"}} {mem_total_mib}")
            lines.append(f"rag_gpu_temperature_celsius{{gpu=\"{gpu}\"}} {temp}")
            lines.append(f"rag_gpu_power_watts{{gpu=\"{gpu}\"}} {power}")

        append_benchmark_metrics(lines)

        body = ("\n".join(lines) + "\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"lm_exporter listening on {HOST}:{PORT}")
    server.serve_forever()
