import json
import tempfile
import unittest
from pathlib import Path

from runtime.cache import MemoryCache, build_exact_cache_key
from runtime.config import RuntimeConfig


class RuntimeTests(unittest.TestCase):
    def test_memory_cache_roundtrip(self) -> None:
        cache = MemoryCache()
        cache.set("x", {"ok": True}, ttl_seconds=60)
        self.assertEqual(cache.get("x"), {"ok": True})

    def test_exact_cache_key_normalization(self) -> None:
        m1 = [{"role": "user", "content": " Hello   RAG "}]
        m2 = [{"role": "user", "content": "hello rag"}]
        k1 = build_exact_cache_key(
            model_alias="rag-main",
            prompt_version="v1",
            retrieval_version="r1",
            top_k=20,
            max_tokens=256,
            messages=m1,
            extra_filters={"tenant": "t1"},
        )
        k2 = build_exact_cache_key(
            model_alias="rag-main",
            prompt_version="v1",
            retrieval_version="r1",
            top_k=20,
            max_tokens=256,
            messages=m2,
            extra_filters={"tenant": "t1"},
        )
        self.assertEqual(k1, k2)

    def test_config_alias_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "model_profiles.json"
            p.write_text(
                json.dumps(
                    {
                        "profiles": {
                            "rag-main": {
                                "model_id": "google/gemma-4-26b-a4b",
                                "context_length": 16384,
                                "parallel": 1,
                                "gpu_binding": "0",
                                "max_tokens": 1024,
                            },
                            "rag-fallback": {
                                "model_id": "google/gemma-4-26b-a4b",
                                "context_length": 8192,
                                "parallel": 1,
                                "gpu_binding": "0",
                                "max_tokens": 512,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            cfg = RuntimeConfig(
                lmstudio_base_url="http://127.0.0.1:1234/v1",
                profile_path=p,
                prompt_version="v1",
                retrieval_version="r1",
                redis_url=None,
                cache_ttl_seconds=60,
                allow_raw_model_id=False,
            )
            self.assertEqual(cfg.resolve_alias("rag-fallback").context_length, 8192)
            self.assertEqual(cfg.resolve_request_model("unknown-model").alias, "rag-main")


if __name__ == "__main__":
    unittest.main()
