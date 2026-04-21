#!/usr/bin/env python3
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BASE_URL = os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
MODELS = [
    model.strip()
    for model in os.environ.get("LMSTUDIO_MODELS", "google/gemma-4-e4b,google/gemma-4-31b").split(",")
    if model.strip()
]
SHORT_REQUESTS = int(os.environ.get("BENCH_SHORT_REQUESTS", "4"))
SHORT_CONCURRENCY = int(os.environ.get("BENCH_SHORT_CONCURRENCY", "2"))
LONG_REQUESTS = int(os.environ.get("BENCH_LONG_REQUESTS", "8"))
LONG_CONCURRENCY = int(os.environ.get("BENCH_LONG_CONCURRENCY", "2"))
LONG_CONTEXT_TARGET_CHARS = int(os.environ.get("BENCH_LONG_CONTEXT_CHARS", "12000"))
SHORT_MAX_TOKENS = int(os.environ.get("BENCH_SHORT_MAX_TOKENS", "192"))
LONG_MAX_TOKENS = int(os.environ.get("BENCH_LONG_MAX_TOKENS", "192"))
TEMPERATURE = float(os.environ.get("BENCH_TEMPERATURE", "0.1"))
RETRIES = int(os.environ.get("BENCH_RETRIES", "2"))
REPORT_JSON = Path(os.environ.get("BENCH_REPORT_JSON", "benchmark_report.json"))
REPORT_MD = Path(os.environ.get("BENCH_REPORT_MD", "benchmark_report.md"))
DEFAULT_METRICS_JSON = Path(__file__).resolve().parent / "monitoring" / "nosudo" / "data" / "benchmark_metrics.json"
METRICS_JSON = Path(os.environ.get("BENCH_METRICS_JSON", str(DEFAULT_METRICS_JSON)))

WARMUP_PROMPT = "请用一句中文说明你是一台用于 RAG 服务压测的模型。"
SHORT_PROMPT = (
    "请用中文回答：\n"
    "1. RAG 系统为什么能降低幻觉？\n"
    "2. 检索、重排、生成三个阶段分别做什么？\n"
    "3. 最后用 3 条要点总结。"
)
LONG_CONTEXT_BLOCK = """
[知识片段]
- RAG 服务链路通常包括：查询预处理、向量检索、重排、上下文拼装、生成回答、引用返回、监控埋点。
- 大上下文请求更容易触发显存上涨、KV Cache 增大、排队时间拉长、首包和总耗时上升。
- 衡量压测效果时，常看成功率、平均返回时间、P95 返回时间、输入 token、输出 token、总 token、输出 token 吞吐、请求吞吐。
- 监控看板需要同时覆盖模型侧指标和机器侧指标，否则只能看到 GPU 忙不忙，看不到业务请求质量。
- 在同一台机器上比较不同模型时，最重要的是统一 prompt 模板、统一上下文长度、统一并发、统一输出上限。
- 当上下文显著变大时，prompt token 往往是主要成本来源；completion token 变化不大，但整体等待时间和吞吐会更敏感。
- 如果压测只看短 prompt，小模型和大模型的差异会被低估；长上下文高并发才能更贴近真实 RAG 检索场景。
""".strip()


@dataclass
class ReqResult:
    ok: bool
    latency_s: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    prompt_chars: int
    text: str
    error: str | None


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * p))))
    return ordered[idx]


def build_long_context(target_chars: int) -> str:
    chunks: list[str] = []
    while sum(len(chunk) for chunk in chunks) < target_chars:
        chunks.append(LONG_CONTEXT_BLOCK)
    return "\n\n".join(chunks)[:target_chars]


def http_json(url: str, payload: dict[str, Any], timeout: int = 300) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _is_retryable(err: str) -> bool:
    err_l = err.lower()
    return any(x in err_l for x in ["http 429", "http 500", "http 502", "http 503", "timed out", "reset"])


def chat_once(model: str, prompt: str, max_tokens: int, temperature: float, retries: int = RETRIES) -> ReqResult:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error: str | None = None
    last_latency = 0.0
    for attempt in range(retries + 1):
        start = time.perf_counter()
        try:
            data = http_json(f"{BASE_URL}/chat/completions", payload, timeout=900)
            latency = time.perf_counter() - start
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
                total_tokens = prompt_tokens + completion_tokens
            return ReqResult(
                ok=True,
                latency_s=latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                prompt_chars=len(prompt),
                text=extract_text(msg.get("content"))[:300],
                error=None,
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:300]
            last_latency = time.perf_counter() - start
            last_error = f"HTTP {exc.code}: {body}"
            if attempt < retries and _is_retryable(last_error):
                time.sleep(0.6 * (attempt + 1))
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last_latency = time.perf_counter() - start
            last_error = str(exc)
            if attempt < retries and _is_retryable(last_error):
                time.sleep(0.6 * (attempt + 1))
                continue
            break

    return ReqResult(
        ok=False,
        latency_s=last_latency,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        prompt_chars=len(prompt),
        text="",
        error=last_error,
    )


def check_models() -> list[str]:
    with urllib.request.urlopen(f"{BASE_URL}/models", timeout=20) as resp:
        data = json.load(resp)
    return [m.get("id", "") for m in data.get("data", [])]


def avg_int(values: list[int | None]) -> float | None:
    nums = [value for value in values if value is not None]
    if not nums:
        return None
    return round(statistics.mean(nums), 2)


def summarize(results: list[ReqResult], concurrency: int, wall_time_s: float, scenario: str) -> dict[str, Any]:
    ok = [r for r in results if r.ok]
    fail = [r for r in results if not r.ok]
    latencies = [r.latency_s for r in ok]
    total_completion_tokens = sum(r.completion_tokens or 0 for r in ok)
    total_prompt_tokens = sum(r.prompt_tokens or 0 for r in ok)
    total_all_tokens = sum(r.total_tokens or 0 for r in ok)
    summary: dict[str, Any] = {
        "scenario": scenario,
        "concurrency": concurrency,
        "total": len(results),
        "ok": len(ok),
        "fail": len(fail),
        "success_rate_pct": round((len(ok) / len(results) * 100) if results else 0.0, 2),
        "wall_time_s": round(wall_time_s, 3),
        "requests_per_second": round((len(ok) / wall_time_s) if wall_time_s > 0 else 0.0, 3),
        "errors": [r.error for r in fail[:10]],
        "prompt_chars_avg": round(statistics.mean(r.prompt_chars for r in results), 1) if results else 0.0,
    }
    if latencies:
        summary["latency_avg_s"] = round(statistics.mean(latencies), 3)
        summary["latency_p95_s"] = round(percentile(latencies, 0.95), 3)
        summary["latency_max_s"] = round(max(latencies), 3)

    prompt_tokens_avg = avg_int([r.prompt_tokens for r in ok])
    completion_tokens_avg = avg_int([r.completion_tokens for r in ok])
    total_tokens_avg = avg_int([r.total_tokens for r in ok])
    if prompt_tokens_avg is not None:
        summary["prompt_tokens_avg"] = prompt_tokens_avg
        summary["prompt_tokens_total"] = total_prompt_tokens
    if completion_tokens_avg is not None:
        summary["completion_tokens_avg"] = completion_tokens_avg
        summary["completion_tokens_total"] = total_completion_tokens
    if total_tokens_avg is not None:
        summary["total_tokens_avg"] = total_tokens_avg
        summary["total_tokens_total"] = total_all_tokens
    if latencies and total_completion_tokens > 0:
        per_request_tps = [(r.completion_tokens / r.latency_s) for r in ok if r.completion_tokens is not None and r.latency_s > 0]
        if per_request_tps:
            summary["output_tokens_per_second_avg"] = round(statistics.mean(per_request_tps), 3)
        summary["output_tokens_per_second_cluster"] = round(total_completion_tokens / wall_time_s if wall_time_s > 0 else 0.0, 3)
    return summary


def run_scenario(model: str, scenario: str, prompt: str, max_tokens: int, concurrency: int, requests: int, temperature: float) -> dict[str, Any]:
    print(
        f"scenario={scenario} model={model} requests={requests} concurrency={concurrency} prompt_chars={len(prompt)} max_tokens={max_tokens}",
        flush=True,
    )
    results: list[ReqResult] = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(chat_once, model, prompt, max_tokens, temperature) for _ in range(requests)]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "ok" if result.ok else "fail"
            print(
                f"  request status={status} latency={result.latency_s:.2f}s prompt_tokens={result.prompt_tokens} completion_tokens={result.completion_tokens}",
                flush=True,
            )
    wall_time_s = time.perf_counter() - started
    summary = summarize(results, concurrency, wall_time_s, scenario)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return {"summary": summary, "samples": [asdict(result) for result in results[: min(5, len(results))]]}


def _long_prompt_with_chars(chars: int) -> str:
    context = build_long_context(chars)
    return (
        "下面是一批与 RAG 平台监控和压测相关的背景材料，请你基于这些内容完成分析。\n\n"
        f"{context}\n\n"
        "任务要求：\n"
        "1. 用中文总结大上下文压测时最该关注的 6 个指标。\n"
        "2. 解释这些指标与 GPU/显存变化的关系。\n"
        "3. 给出 4 条优化建议。\n"
        "4. 输出要有明确标题和条目，不要复述原文。\n"
    )


def choose_stable_long_prompt(model: str) -> tuple[str, int]:
    candidates = [
        LONG_CONTEXT_TARGET_CHARS,
        int(LONG_CONTEXT_TARGET_CHARS * 0.75),
        int(LONG_CONTEXT_TARGET_CHARS * 0.5),
        int(LONG_CONTEXT_TARGET_CHARS * 0.35),
        3000,
        1800,
    ]
    tried = []
    for chars in candidates:
        chars = max(1000, chars)
        prompt = _long_prompt_with_chars(chars)
        probe = chat_once(model, prompt, max_tokens=min(96, LONG_MAX_TOKENS), temperature=0.0, retries=0)
        tried.append((chars, probe.ok, probe.error))
        if probe.ok:
            print(f"long-context probe selected chars={chars}", flush=True)
            return prompt, chars
    print(f"long-context probe fallback chars=1200 tried={tried}", flush=True)
    return _long_prompt_with_chars(1200), 1200


def run_model(model: str) -> dict[str, Any]:
    print(f"\n=== Benchmark {model} ===", flush=True)
    warmup = chat_once(model, WARMUP_PROMPT, max_tokens=64, temperature=0.0)
    print(
        f"warmup ok={warmup.ok} latency={warmup.latency_s:.2f}s prompt_tokens={warmup.prompt_tokens} completion_tokens={warmup.completion_tokens}",
        flush=True,
    )

    short_result = run_scenario(
        model=model,
        scenario="短上下文基线",
        prompt=SHORT_PROMPT,
        max_tokens=SHORT_MAX_TOKENS,
        concurrency=SHORT_CONCURRENCY,
        requests=SHORT_REQUESTS,
        temperature=TEMPERATURE,
    )

    long_prompt, selected_chars = choose_stable_long_prompt(model)
    long_result = run_scenario(
        model=model,
        scenario=f"长上下文压测(chars={selected_chars})",
        prompt=long_prompt,
        max_tokens=LONG_MAX_TOKENS,
        concurrency=LONG_CONCURRENCY,
        requests=LONG_REQUESTS,
        temperature=TEMPERATURE,
    )

    return {
        "model": model,
        "warmup": {
            "ok": warmup.ok,
            "latency_s": round(warmup.latency_s, 3),
            "prompt_tokens": warmup.prompt_tokens,
            "completion_tokens": warmup.completion_tokens,
            "error": warmup.error,
        },
        "scenarios": [short_result, long_result],
    }


def build_metrics_payload(report: dict[str, Any]) -> dict[str, Any]:
    scenario_metrics: list[dict[str, Any]] = []
    latest_timestamp = report["timestamp"]
    for model_entry in report["models"]:
        model = model_entry["model"]
        for scenario_entry in model_entry["scenarios"]:
            summary = scenario_entry["summary"]
            scenario_metrics.append(
                {
                    "model": model,
                    "scenario": summary["scenario"],
                    "metrics": {
                        "concurrency": summary["concurrency"],
                        "requests_total": summary["total"],
                        "requests_ok": summary["ok"],
                        "requests_fail": summary["fail"],
                        "success_rate_pct": summary["success_rate_pct"],
                        "wall_time_s": summary["wall_time_s"],
                        "requests_per_second": summary["requests_per_second"],
                        "prompt_chars_avg": summary["prompt_chars_avg"],
                        "latency_avg_s": summary.get("latency_avg_s"),
                        "latency_p95_s": summary.get("latency_p95_s"),
                        "latency_max_s": summary.get("latency_max_s"),
                        "prompt_tokens_avg": summary.get("prompt_tokens_avg"),
                        "prompt_tokens_total": summary.get("prompt_tokens_total"),
                        "completion_tokens_avg": summary.get("completion_tokens_avg"),
                        "completion_tokens_total": summary.get("completion_tokens_total"),
                        "total_tokens_avg": summary.get("total_tokens_avg"),
                        "total_tokens_total": summary.get("total_tokens_total"),
                        "output_tokens_per_second_avg": summary.get("output_tokens_per_second_avg"),
                        "output_tokens_per_second_cluster": summary.get("output_tokens_per_second_cluster"),
                    },
                }
            )
    return {
        "timestamp": latest_timestamp,
        "base_url": report["base_url"],
        "models_total": len(report["models"]),
        "long_context_target_chars": LONG_CONTEXT_TARGET_CHARS,
        "scenario_metrics": scenario_metrics,
    }


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# LM Studio 大上下文压测报告",
        "",
        f"- base_url: {report['base_url']}",
        f"- timestamp: {report['timestamp']}",
        f"- long_context_target_chars: {report['long_context_target_chars']}",
        "",
    ]
    for model_entry in report["models"]:
        lines.append(f"## {model_entry['model']}")
        lines.append(f"- warmup: {model_entry['warmup']}")
        for scenario in model_entry["scenarios"]:
            summary = scenario["summary"]
            lines.append(f"- {summary['scenario']}: {json.dumps(summary, ensure_ascii=False)}")
        lines.append("")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    model_ids = check_models()
    missing = [model for model in MODELS if model not in model_ids]
    if missing:
        raise SystemExit(f"Missing models in API list: {missing}. Available: {model_ids}")

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    METRICS_JSON.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "base_url": BASE_URL,
        "timestamp": int(time.time()),
        "long_context_target_chars": LONG_CONTEXT_TARGET_CHARS,
        "short_requests": SHORT_REQUESTS,
        "short_concurrency": SHORT_CONCURRENCY,
        "long_requests": LONG_REQUESTS,
        "long_concurrency": LONG_CONCURRENCY,
        "models": [run_model(model) for model in MODELS],
    }

    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report)
    METRICS_JSON.write_text(json.dumps(build_metrics_payload(report), ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nBenchmark finished. Reports:")
    print(f"- {REPORT_JSON}")
    print(f"- {REPORT_MD}")
    print(f"- {METRICS_JSON}")


if __name__ == "__main__":
    main()
