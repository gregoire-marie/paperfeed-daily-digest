from __future__ import annotations

import json
import unittest
from unittest import mock

from paperfeed.models import LlamaCppConfig, Paper, PaperAuthor
from paperfeed.summarize import LlamaCppSummarizer, create_summarizer


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class SummarizeTests(unittest.TestCase):
    def test_create_summarizer_defaults_to_deterministic(self) -> None:
        summarizer = create_summarizer()
        self.assertEqual(summarizer.__class__.__name__, "DeterministicSummarizer")

    def test_llama_cpp_summarizer_calls_local_chat_completion_api(self) -> None:
        paper = Paper(
            paper_id="paper-1",
            title="Adaptive Research Digest Ranking",
            abstract=(
                "We introduce an adaptive digest ranking method for research discovery. "
                "The approach uses lightweight personalization over recommendation candidates. "
                "Results show better novelty and click-through than a non-adaptive baseline."
            ),
            authors=[PaperAuthor(name="Alice"), PaperAuthor(name="Bob")],
            year=2026,
            citation_count=4,
        )
        seed_papers = [
            Paper(
                paper_id="seed-1",
                title="Research Digest Ranking with Recommendations",
            )
        ]

        def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
            self.assertEqual(timeout, 15.0)
            self.assertEqual(getattr(request, "full_url"), "http://127.0.0.1:8081/v1/chat/completions")
            payload = json.loads(getattr(request, "data").decode("utf-8"))
            self.assertEqual(payload["model"], "qwen2.5-7b-instruct")
            self.assertEqual(payload["temperature"], 0.2)
            self.assertEqual(payload["messages"][0]["role"], "system")
            return _FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "why_it_matters": "It is close to the digest-ranking seed papers.",
                                        "main_idea": "The paper adapts ranking for daily research digests.",
                                        "method": "It applies lightweight personalization to recommendation candidates.",
                                        "key_results": "It improves novelty and click-through over a baseline.",
                                        "limitations": "The summary is constrained by the abstract and omits full evaluation details.",
                                        "relevance_to_my_research": "It is directly relevant if you are tuning digest ranking or recommendation filtering.",
                                    }
                                )
                            }
                        }
                    ]
                }
            )

        summarizer = LlamaCppSummarizer(
            LlamaCppConfig(
                base_url="http://127.0.0.1:8081/v1",
                model="qwen2.5-7b-instruct",
                temperature=0.2,
                timeout_seconds=15.0,
            )
        )

        with mock.patch("paperfeed.summarize.urlopen", side_effect=fake_urlopen):
            summary = summarizer.summarize_paper(paper, seed_papers)

        self.assertEqual(summary.basis, "abstract-only")
        self.assertEqual(
            summary.main_idea,
            "The paper adapts ranking for daily research digests.",
        )


if __name__ == "__main__":
    unittest.main()
