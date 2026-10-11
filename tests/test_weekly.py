from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from paperfeed.run_weekly import DigestAlreadyExistsError, main, run_weekly, weekly_digest_date


class WeeklyTests(unittest.TestCase):
    def test_manual_runs_share_the_most_recent_sunday(self) -> None:
        for day in range(11, 18):
            with self.subTest(day=day):
                self.assertEqual(weekly_digest_date(date(2026, 10, day)), date(2026, 10, 11))
        self.assertEqual(weekly_digest_date(date(2026, 10, 18)), date(2026, 10, 18))
        self.assertEqual(weekly_digest_date(date(2027, 1, 1)), date(2026, 12, 27))

    def test_existing_report_is_preserved_before_config_or_api_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            digest = root / "site" / "digests" / "2026-10-11.html"
            digest.parent.mkdir(parents=True)
            digest.write_text("Preserved imported report", encoding="utf-8")
            client = mock.Mock()
            with self.assertRaises(DigestAlreadyExistsError):
                run_weekly(
                    config_path=root / "missing.yaml", site_dir=root / "site",
                    seen_path=root / "seen.json", digest_date=date(2026, 10, 11), client=client,
                )
            client.resolve_seed.assert_not_called()
            self.assertEqual(digest.read_text(), "Preserved imported report")
            self.assertFalse((root / "seen.json").exists())
            with mock.patch("paperfeed.run_weekly.SemanticScholarClient") as client_class:
                self.assertEqual(main(["--date", "2026-10-11", "--site-dir", str(root / "site")]), 0)
            client_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
