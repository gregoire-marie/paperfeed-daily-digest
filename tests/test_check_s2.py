from __future__ import annotations

import io
import os
from pathlib import Path
import unittest
from unittest import mock

from paperfeed.check_s2 import EXAMPLE_PAPER_ID, main
from paperfeed.models import Paper
from paperfeed.semantic_scholar import SeedResolutionError, SemanticScholarError


class CheckS2Tests(unittest.TestCase):
    def test_prompted_key_is_used_instead_of_environment_and_not_printed(self) -> None:
        output = io.StringIO()
        with (
            mock.patch("paperfeed.check_s2.sys.stdin.isatty", return_value=True),
            mock.patch("paperfeed.check_s2.getpass", return_value="  supplied-secret  "),
            mock.patch.dict(os.environ, {"S2_API_KEY": "old-secret"}),
            mock.patch("paperfeed.check_s2.SemanticScholarClient") as client_class,
            mock.patch("sys.stdout", output),
        ):
            client_class.return_value.resolve_seed.return_value = Paper(
                paper_id=EXAMPLE_PAPER_ID, title="Known paper",
            )
            result = main([])

        self.assertEqual(result, 0)
        client_class.assert_called_once_with(api_key="supplied-secret")
        self.assertEqual(
            client_class.return_value.resolve_seed.call_args.args[0].paper_id,
            EXAMPLE_PAPER_ID,
        )
        client_class.return_value.get_recommendations.assert_not_called()
        self.assertNotIn("supplied-secret", output.getvalue())
        self.assertNotIn("old-secret", output.getvalue())

    def test_api_failure_redacts_key_from_error_output(self) -> None:
        error_output = io.StringIO()
        with (
            mock.patch("paperfeed.check_s2.sys.stdin.isatty", return_value=True),
            mock.patch("paperfeed.check_s2.getpass", return_value="supplied-secret"),
            mock.patch("paperfeed.check_s2.SemanticScholarClient") as client_class,
            mock.patch("sys.stdout", io.StringIO()),
            mock.patch("sys.stderr", error_output),
        ):
            client_class.return_value.resolve_seed.side_effect = SemanticScholarError(
                "HTTP 401 for supplied-secret",
            )
            result = main([])

        self.assertEqual(result, 1)
        self.assertIn("HTTP 401", error_output.getvalue())
        self.assertIn("[redacted]", error_output.getvalue())
        self.assertNotIn("supplied-secret", error_output.getvalue())

    def test_configured_discovery_skips_unindexed_seed_and_checks_recommendations(self) -> None:
        output = io.StringIO()
        with (
            mock.patch("paperfeed.check_s2.sys.stdin.isatty", return_value=True),
            mock.patch("paperfeed.check_s2.getpass", return_value="supplied-secret"),
            mock.patch("paperfeed.check_s2.SemanticScholarClient") as client_class,
            mock.patch("sys.stdout", output),
        ):
            client = client_class.return_value
            client.resolve_seed.side_effect = [
                Paper(paper_id=EXAMPLE_PAPER_ID, title="Known paper"),
                SeedResolutionError("Not indexed"),
                Paper(paper_id="seed-2", title="Indexed seed"),
            ]
            client.get_recommendations.return_value = []
            config_path = Path(__file__).resolve().parents[1] / "seeds.yaml"
            result = main(["--config", str(config_path)])

        self.assertEqual(result, 0)
        client.get_recommendations.assert_called_once_with(["seed-2"], [], limit=1)
        self.assertIn("Skipping unresolved positive seed", output.getvalue())

    def test_invalid_key_fails_before_any_api_request(self) -> None:
        for key in ("", "S2 API Key: supplied-secret", '"supplied-secret"'):
            with (
                self.subTest(key=key),
                mock.patch("paperfeed.check_s2.sys.stdin.isatty", return_value=True),
                mock.patch("paperfeed.check_s2.getpass", return_value=key),
                mock.patch("paperfeed.check_s2.SemanticScholarClient") as client_class,
                mock.patch("sys.stderr", io.StringIO()),
            ):
                self.assertEqual(main([]), 1)
                client_class.assert_not_called()

    def test_noninteractive_input_does_not_echo_or_read_key(self) -> None:
        with (
            mock.patch("paperfeed.check_s2.sys.stdin.isatty", return_value=False),
            mock.patch("paperfeed.check_s2.getpass") as prompt,
            mock.patch("sys.stderr", io.StringIO()),
        ):
            self.assertEqual(main([]), 1)
        prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
