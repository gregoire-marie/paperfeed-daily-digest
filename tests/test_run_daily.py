from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from paperfeed.models import Paper, PaperAuthor, PaperSeed, PaperSummary
from paperfeed.run_daily import NoUsablePositiveSeedsError, run_daily
from paperfeed.semantic_scholar import SeedResolutionError


class FakeDiscoveryClient:
    def __init__(self) -> None:
        self.seed_paper = Paper(
            paper_id="seed-1",
            title="Efficient Retrieval for Research Digests",
            abstract="A seed paper about retrieval for research digests.",
            authors=[PaperAuthor(name="Seed Author")],
            year=2025,
            url="https://www.semanticscholar.org/paper/seed-1",
        )
        self.candidates = [
            Paper(
                paper_id="candidate-1",
                title="Retrieval-Augmented Daily Research Feeds",
                abstract=(
                    "We present a daily research feed system for focused discovery. "
                    "Our method combines recommendation ranking with lightweight filtering. "
                    "Results show better novelty and lower duplication than a baseline feed."
                ),
                authors=[PaperAuthor(name="Alice"), PaperAuthor(name="Bob")],
                venue="ArXiv",
                year=2026,
                publication_date="2026-03-20",
                url="https://www.semanticscholar.org/paper/candidate-1",
                pdf_url="https://example.com/candidate-1.pdf",
                doi="10.1000/candidate-1",
                citation_count=12,
            ),
            Paper(
                paper_id="candidate-2",
                title="Older Paper That Should Be Filtered",
                abstract="We present an older paper.",
                authors=[PaperAuthor(name="Charlie")],
                year=2022,
                url="https://www.semanticscholar.org/paper/candidate-2",
                doi="10.1000/candidate-2",
                citation_count=99,
            ),
        ]

    def resolve_seed(self, seed: PaperSeed) -> Paper:
        return self.seed_paper

    def get_recommendations(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str],
        limit: int,
    ) -> list[Paper]:
        return self.candidates[:limit]


class FakeSummarizer:
    def summarize_paper(self, paper: Paper, seed_papers: list[Paper]) -> PaperSummary:
        return PaperSummary(
            basis="abstract-only",
            why_it_matters="Custom backend summary.",
            main_idea=f"Focused summary for {paper.title}.",
            method="Custom method section.",
            key_results="Custom results section.",
            limitations="Custom limitations section.",
            relevance_to_my_research="Custom relevance section.",
        )


class PartiallyResolvableDiscoveryClient(FakeDiscoveryClient):
    def resolve_seed(self, seed: PaperSeed) -> Paper:
        if seed.doi == "10.1000/missing":
            raise SeedResolutionError("Missing seed in Semantic Scholar.")
        return super().resolve_seed(seed)


class UnresolvableDiscoveryClient(FakeDiscoveryClient):
    def resolve_seed(self, seed: PaperSeed) -> Paper:
        raise SeedResolutionError(f"Missing seed {seed.identifier}.")

    def get_recommendations(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str],
        limit: int,
    ) -> list[Paper]:
        raise AssertionError("Recommendations should not be requested without positive seeds.")


class RunDailyTests(unittest.TestCase):
    def test_run_daily_builds_digest_and_updates_seen_state(self) -> None:
        fake_client = FakeDiscoveryClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "seeds.yaml"
            seen_path = root / "data" / "seen.json"
            site_dir = root / "site"
            config_path.write_text(
                """
positive_seeds:
  - paper_id: "seed-1"

negative_seeds: []

preferences:
  top_k: 2
  max_candidates_per_seed: 10
  min_publication_year: 2023
""".strip()
                + "\n",
                encoding="utf-8",
            )

            result = run_daily(
                config_path=config_path,
                seen_path=seen_path,
                site_dir=site_dir,
                digest_date=date(2026, 3, 23),
                client=fake_client,
            )

            self.assertEqual(result.candidate_count, 2)
            self.assertEqual(result.unseen_count, 1)
            self.assertEqual(result.selected_count, 1)
            self.assertTrue((site_dir / "index.html").exists())
            self.assertTrue((site_dir / "digests" / "2026-03-23.html").exists())

            seen_payload = json.loads(seen_path.read_text(encoding="utf-8"))
            self.assertEqual(len(seen_payload["papers"]), 1)
            self.assertEqual(seen_payload["papers"][0]["paper_id"], "candidate-1")

    def test_run_daily_accepts_custom_summarizer_backend(self) -> None:
        fake_client = FakeDiscoveryClient()
        fake_summarizer = FakeSummarizer()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "seeds.yaml"
            seen_path = root / "data" / "seen.json"
            site_dir = root / "site"
            config_path.write_text(
                """
positive_seeds:
  - paper_id: "seed-1"

negative_seeds: []

preferences:
  top_k: 1
  max_candidates_per_seed: 10
""".strip()
                + "\n",
                encoding="utf-8",
            )

            result = run_daily(
                config_path=config_path,
                seen_path=seen_path,
                site_dir=site_dir,
                digest_date=date(2026, 3, 23),
                client=fake_client,
                summarizer=fake_summarizer,
            )

            self.assertEqual(result.selected_count, 1)
            self.assertEqual(
                result.digest.entries[0].summary.why_it_matters,
                "Custom backend summary.",
            )

    def test_run_daily_skips_unresolvable_seeds_when_others_work(self) -> None:
        fake_client = PartiallyResolvableDiscoveryClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "seeds.yaml"
            seen_path = root / "data" / "seen.json"
            site_dir = root / "site"
            config_path.write_text(
                """
positive_seeds:
  - paper_id: "seed-1"
  - doi: "10.1000/missing"

negative_seeds: []

preferences:
  top_k: 1
  max_candidates_per_seed: 10
""".strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertLogs("paperfeed.run_daily", level="WARNING") as captured_logs:
                result = run_daily(
                    config_path=config_path,
                    seen_path=seen_path,
                    site_dir=site_dir,
                    digest_date=date(2026, 3, 23),
                    client=fake_client,
                )

            self.assertEqual(len(result.resolved_positive_seeds), 1)
            self.assertEqual(result.resolved_positive_seeds[0].paper_id, "seed-1")
            self.assertEqual(result.selected_count, 1)
            self.assertEqual(len(captured_logs.output), 1)
            self.assertIn("Skipping positive seed '10.1000/missing'", captured_logs.output[0])

    def test_run_daily_fails_clearly_when_no_positive_seed_resolves(self) -> None:
        fake_client = UnresolvableDiscoveryClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "seeds.yaml"
            seen_path = root / "data" / "seen.json"
            site_dir = root / "site"
            config_path.write_text(
                """
positive_seeds:
  - doi: "10.1000/missing"

negative_seeds: []
""".strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertLogs("paperfeed.run_daily", level="WARNING") as captured_logs:
                with self.assertRaisesRegex(
                    NoUsablePositiveSeedsError,
                    "None of the configured positive seeds could be resolved",
                ):
                    run_daily(
                        config_path=config_path,
                        seen_path=seen_path,
                        site_dir=site_dir,
                        digest_date=date(2026, 3, 23),
                        client=fake_client,
                    )

            self.assertEqual(len(captured_logs.output), 1)
            self.assertIn("Skipping positive seed '10.1000/missing'", captured_logs.output[0])


if __name__ == "__main__":
    unittest.main()
