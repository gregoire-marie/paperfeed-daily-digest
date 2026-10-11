from __future__ import annotations

import unittest
from unittest import mock
from urllib.error import HTTPError

from paperfeed.models import PaperSeed
from paperfeed.semantic_scholar import (
    SeedResolutionError,
    SemanticScholarClient,
    SemanticScholarNotFoundError,
)


class SemanticScholarClientTests(unittest.TestCase):
    def test_seed_and_recommendations_share_rate_limit_and_api_key(self) -> None:
        client = SemanticScholarClient(api_key="test-key")
        response = mock.MagicMock()
        response.__enter__.return_value.read.side_effect = [
            b'{"paperId":"seed-1","title":"Seed"}',
            b'{"recommendedPapers":[]}',
        ]

        with (
            mock.patch("paperfeed.semantic_scholar.urlopen", return_value=response) as urlopen,
            mock.patch("paperfeed.semantic_scholar.time.monotonic", side_effect=[0.0, 0.25, 1.1]),
            mock.patch("paperfeed.semantic_scholar.time.sleep") as sleep,
        ):
            seed = client.resolve_seed(PaperSeed(paper_id="seed-1"))
            recommendations = client.get_recommendations([seed.paper_id], [], 5)

        self.assertEqual(recommendations, [])
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 0.85)
        requests = [call.args[0] for call in urlopen.call_args_list]
        self.assertEqual([request.method for request in requests], ["GET", "POST"])
        for request in requests:
            self.assertEqual(request.get_header("X-api-key"), "test-key")

    def test_slow_requests_need_no_extra_wait(self) -> None:
        client = SemanticScholarClient()
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"recommendedPapers":[]}'

        with (
            mock.patch("paperfeed.semantic_scholar.urlopen", return_value=response),
            mock.patch("paperfeed.semantic_scholar.time.monotonic", side_effect=[0.0, 2.0, 2.0]),
            mock.patch("paperfeed.semantic_scholar.time.sleep") as sleep,
        ):
            client.get_recommendations(["seed-1"], [], 5)
            client.get_recommendations(["seed-1"], [], 5)

        sleep.assert_not_called()

    def test_missing_seed_still_counts_toward_rate_limit(self) -> None:
        client = SemanticScholarClient()
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"recommendedPapers":[]}'
        error = HTTPError("https://api.semanticscholar.org", 404, "Not found", {}, None)

        with (
            mock.patch("paperfeed.semantic_scholar.urlopen", side_effect=[error, response]),
            mock.patch("paperfeed.semantic_scholar.time.monotonic", side_effect=[0.0, 0.1, 1.1]),
            mock.patch("paperfeed.semantic_scholar.time.sleep") as sleep,
        ):
            with self.assertRaises(SeedResolutionError):
                client.resolve_seed(PaperSeed(paper_id="missing"))
            client.get_recommendations(["seed-1"], [], 5)

        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 1.0)

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
