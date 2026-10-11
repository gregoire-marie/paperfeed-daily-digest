from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock
from urllib.error import HTTPError

from paperfeed.models import PaperSeed
from paperfeed.semantic_scholar import (
    SeedResolutionError,
    SemanticScholarClient,
    SemanticScholarError,
    SemanticScholarNotFoundError,
)


class SemanticScholarClientTests(unittest.TestCase):
    def test_recommendations_require_an_explicit_array_of_paper_objects(self) -> None:
        for payload in ({}, {"error": "Unavailable"}, {"recommendedPapers": None}, {"recommendedPapers": {}}, {"recommendedPapers": [None]}):
            with self.subTest(payload=payload):
                client = SemanticScholarClient()
                with mock.patch.object(client, "_request_json", return_value=payload):
                    with self.assertRaisesRegex(SemanticScholarError, "recommendedPapers array"):
                        client.get_recommendations(["seed-1"], [], 5)

    def test_recommendations_log_explicit_empty_response_and_seed_ids(self) -> None:
        client = SemanticScholarClient()
        with (
            mock.patch.object(client, "_request_json", return_value={"recommendedPapers": []}) as request,
            self.assertLogs("paperfeed.semantic_scholar", level="INFO") as logs,
        ):
            self.assertEqual(client.get_recommendations(["seed-1", "seed-2"], [], 40), [])
        self.assertEqual(request.call_args.kwargs["body"]["positivePaperIds"], ["seed-1", "seed-2"])
        self.assertIn("positive_ids=seed-1,seed-2", logs.output[0])
        self.assertIn("returned=0", logs.output[0])

    def test_non_object_json_response_fails_clearly(self) -> None:
        client = SemanticScholarClient()
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'[]'
        with mock.patch("paperfeed.semantic_scholar.urlopen", return_value=response):
            with self.assertRaisesRegex(SemanticScholarError, "JSON object"):
                client.get_recommendations(["seed-1"], [], 5)

    def test_transient_429_retries_get_and_post_without_changing_request(self) -> None:
        for method in ("GET", "POST"):
            with self.subTest(method=method):
                client = SemanticScholarClient(api_key="test-key")
                response = mock.MagicMock()
                response.__enter__.return_value.read.return_value = (
                    b'{"paperId":"seed-1","title":"Seed"}'
                    if method == "GET"
                    else b'{"recommendedPapers":[]}'
                )
                errors = [
                    HTTPError("https://api.semanticscholar.org", 429, "Rate limited", {}, None)
                    for _ in range(2)
                ]

                with (
                    mock.patch("paperfeed.semantic_scholar.urlopen", side_effect=[*errors, response]) as urlopen,
                    mock.patch.object(client, "_wait_for_rate_limit") as pace,
                    mock.patch("paperfeed.semantic_scholar.time.sleep") as sleep,
                    self.assertLogs("paperfeed.semantic_scholar", level="WARNING") as logs,
                ):
                    if method == "GET":
                        self.assertEqual(client.resolve_seed(PaperSeed(paper_id="seed-1")).paper_id, "seed-1")
                    else:
                        self.assertEqual(client.get_recommendations(["seed-1"], [], 5), [])

                self.assertEqual(sleep.call_args_list, [mock.call(5.0), mock.call(10.0)])
                self.assertEqual(pace.call_count, 3)
                requests = [call.args[0] for call in urlopen.call_args_list]
                self.assertTrue(all(request is requests[0] for request in requests))
                self.assertEqual(requests[0].get_header("X-api-key"), "test-key")
                self.assertNotIn("test-key", " ".join(logs.output))

    def test_persistent_429_stops_after_five_attempts(self) -> None:
        client = SemanticScholarClient()
        errors = [
            HTTPError("https://api.semanticscholar.org", 429, "Rate limited", {}, None)
            for _ in range(5)
        ]
        with (
            mock.patch("paperfeed.semantic_scholar.urlopen", side_effect=errors) as urlopen,
            mock.patch.object(client, "_wait_for_rate_limit") as pace,
            mock.patch("paperfeed.semantic_scholar.time.sleep") as sleep,
            self.assertLogs("paperfeed.semantic_scholar", level="WARNING"),
        ):
            with self.assertRaisesRegex(SemanticScholarError, "After 5 attempts"):
                client.resolve_seed(PaperSeed(paper_id="seed-1"))

        self.assertEqual(urlopen.call_count, 5)
        self.assertEqual(pace.call_count, 5)
        self.assertEqual(sleep.call_args_list, [mock.call(delay) for delay in (5.0, 10.0, 20.0, 40.0)])

    def test_retry_after_respects_seconds_and_http_dates(self) -> None:
        cases = [
            ("12", 12.0),
            ("Sun, 11 Oct 2026 15:00:30 GMT", 30.0),
            ("Sun, 11 Oct 2026 14:59:00 GMT", 5.0),
            ("1", 5.0),
            ("invalid", 5.0),
        ]
        for retry_after, expected_delay in cases:
            with self.subTest(retry_after=retry_after):
                client = SemanticScholarClient()
                error = HTTPError(
                    "https://api.semanticscholar.org", 429, "Rate limited",
                    {"Retry-After": retry_after}, None,
                )
                response = mock.MagicMock()
                response.__enter__.return_value.read.return_value = b'{"recommendedPapers":[]}'
                with (
                    mock.patch("paperfeed.semantic_scholar.urlopen", side_effect=[error, response]),
                    mock.patch.object(client, "_wait_for_rate_limit"),
                    mock.patch("paperfeed.semantic_scholar.time.sleep") as sleep,
                    mock.patch("paperfeed.semantic_scholar.datetime") as clock,
                    self.assertLogs("paperfeed.semantic_scholar", level="WARNING"),
                ):
                    clock.now.return_value = datetime(2026, 10, 11, 15, 0, tzinfo=timezone.utc)
                    client.get_recommendations(["seed-1"], [], 5)

                sleep.assert_called_once_with(expected_delay)

    def test_non_rate_limit_http_errors_fail_without_retries(self) -> None:
        for code in (400, 401, 403, 500):
            with self.subTest(code=code):
                client = SemanticScholarClient()
                error = HTTPError("https://api.semanticscholar.org", code, "Failure", {}, None)
                with (
                    mock.patch("paperfeed.semantic_scholar.urlopen", side_effect=error) as urlopen,
                    mock.patch("paperfeed.semantic_scholar.time.sleep") as sleep,
                ):
                    with self.assertRaisesRegex(SemanticScholarError, f"HTTP {code}"):
                        client.resolve_seed(PaperSeed(paper_id="seed-1"))

                self.assertEqual(urlopen.call_count, 1)
                sleep.assert_not_called()

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
                "indexed under its Semantic Scholar paper_id without a working DOI lookup",
            ):
                client.resolve_seed(PaperSeed(doi="10.13009/EUCASS2025-284"))


if __name__ == "__main__":
    unittest.main()
