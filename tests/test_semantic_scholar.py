from __future__ import annotations

import unittest
from unittest import mock

from paperfeed.models import PaperSeed
from paperfeed.semantic_scholar import (
    SeedResolutionError,
    SemanticScholarClient,
    SemanticScholarNotFoundError,
)


class SemanticScholarClientTests(unittest.TestCase):
    def test_resolve_seed_uses_normalized_doi_identifier(self) -> None:
        client = SemanticScholarClient()
        payload = {
            "paperId": "seed-1",
            "title": "Normalized DOI Seed",
            "authors": [],
            "externalIds": {"DOI": "10.13009/eucass2025-284"},
        }

        with mock.patch.object(client, "_request_json", return_value=payload) as request_json:
            paper = client.resolve_seed(PaperSeed(doi="10.13009/EUCASS2025-284"))

        self.assertEqual(paper.paper_id, "seed-1")
        self.assertEqual(
            request_json.call_args.kwargs["url"],
            "https://api.semanticscholar.org/graph/v1/paper/DOI:10.13009%2Feucass2025-284",
        )

    def test_resolve_seed_raises_clear_error_for_missing_doi(self) -> None:
        client = SemanticScholarClient()

        with mock.patch.object(
            client,
            "_request_json",
            side_effect=SemanticScholarNotFoundError(
                "https://api.semanticscholar.org/graph/v1/paper/DOI:10.13009%2Feucass2025-284",
                '{"error":"Paper with id DOI:10.13009/eucass2025-284 not found"}',
            ),
        ):
            with self.assertRaisesRegex(
                SeedResolutionError,
                "doi.org without being indexed by Semantic Scholar",
            ):
                client.resolve_seed(PaperSeed(doi="10.13009/EUCASS2025-284"))


if __name__ == "__main__":
    unittest.main()
