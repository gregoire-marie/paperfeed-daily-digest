from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paperfeed.config import load_config, load_summarizer_config


class ConfigTests(unittest.TestCase):
    def test_load_config_from_yaml_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "seeds.yaml"
            config_path.write_text(
                """
positive_seeds:
  - doi: "10.1000/test"
  - paper_id: "abc123"

negative_seeds:
  - paper_id: "neg456"

preferences:
  top_k: 3
  max_candidates_per_seed: 15
  min_publication_year: 2024
""".strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(len(config.positive_seeds), 2)
            self.assertEqual(config.positive_seeds[0].doi, "10.1000/test")
            self.assertEqual(config.positive_seeds[1].paper_id, "abc123")
            self.assertEqual(config.negative_seeds[0].paper_id, "neg456")
            self.assertEqual(config.preferences.top_k, 3)
            self.assertEqual(config.preferences.max_candidates_per_seed, 15)
            self.assertEqual(config.preferences.min_publication_year, 2024)

    def test_load_summarizer_config_reads_llama_cpp_environment(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "PAPERFEED_SUMMARIZER_BACKEND": "llama-cpp",
                "LLAMA_CPP_BASE_URL": "http://127.0.0.1:8081/v1",
                "LLAMA_CPP_MODEL": "qwen2.5-7b-instruct",
                "LLAMA_CPP_API_KEY": "local-secret",
                "LLAMA_CPP_TEMPERATURE": "0.25",
                "LLAMA_CPP_TIMEOUT_SECONDS": "15",
            },
            clear=False,
        ):
            config = load_summarizer_config()

        self.assertEqual(config.backend, "llama-cpp")
        self.assertEqual(config.llama_cpp.base_url, "http://127.0.0.1:8081/v1")
        self.assertEqual(config.llama_cpp.model, "qwen2.5-7b-instruct")
        self.assertEqual(config.llama_cpp.api_key, "local-secret")
        self.assertEqual(config.llama_cpp.temperature, 0.25)
        self.assertEqual(config.llama_cpp.timeout_seconds, 15.0)

    def test_load_config_normalizes_doi_seed_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "seeds.yaml"
            config_path.write_text(
                """
positive_seeds:
  - doi: "https://doi.org/10.13009/EUCASS2025-284"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.positive_seeds[0].doi, "10.13009/eucass2025-284")


if __name__ == "__main__":
    unittest.main()
