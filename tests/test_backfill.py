from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest

from paperfeed.backfill import backfill_reports, load_reports

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "backfill" / "manifest.json"


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.images: list[str] = []
        self.links: set[str] = set()

    def handle_data(self, data: str) -> None:
        self.text.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "img":
            self.text.append(values.get("alt") or "")
            self.images.append(values.get("src") or "")
        if tag == "a" and values.get("href"):
            self.links.add(values["href"])


class BackfillTests(unittest.TestCase):
    def test_all_reports_items_characters_formulas_and_sources_are_preserved(self) -> None:
        reports = load_reports(MANIFEST)
        manifest = json.loads(MANIFEST.read_text())
        self.assertEqual(len(reports), 12)
        self.assertEqual(sum(report.item_count for report in reports), 60)
        for report, audit in zip(reports, manifest["reports"]):
            with self.subTest(date=report.report_date):
                self.assertEqual(report.report_date.weekday(), 6)
                self.assertEqual(report.html.count('<article class="panel paper-card'), 5)
                parser = VisibleText()
                parser.feed(report.html)
                original = (MANIFEST.parent / "reports" / f"{report.report_date}.txt").read_text()
                count = lambda text: Counter(c for c in text if not c.isspace() and c != "•")
                self.assertEqual(count(original), count("".join(parser.text)))
                self.assertEqual(len(parser.images), audit["formula_count"])
                self.assertTrue(set(audit["source_links"]).issubset(parser.links))
                for image in parser.images:
                    self.assertTrue((ROOT / "site" / "digests" / image).resolve().is_file())

    def test_rebuilding_is_idempotent_and_preserves_existing_repository_papers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            site = root / "site"
            seen = root / "seen.json"
            first = backfill_reports(manifest_path=MANIFEST, site_dir=site, seen_path=seen)
            snapshot = {path: path.read_bytes() for path in first + [site / "index.html", seen]}
            second = backfill_reports(manifest_path=MANIFEST, site_dir=site, seen_path=seen)
            self.assertEqual(first, second)
            self.assertEqual(snapshot, {path: path.read_bytes() for path in snapshot})
            today = (site / "digests" / "2026-10-11.html").read_text()
            existing = (MANIFEST.parent / "reports" / "2026-10-11-repo.html").read_text()
            self.assertIn(existing, today)
            self.assertEqual(today.count('<article class="panel paper-card'), 10)
            records = json.loads(seen.read_text())["papers"]
            self.assertEqual(len({item["title_hash"] for item in records}), len(records))
            self.assertEqual(len(records), 60)

    def test_changed_transcription_is_rejected_before_any_output_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            import shutil
            shutil.copytree(MANIFEST.parent, root / "backfill")
            report = root / "backfill" / "reports" / "2026-07-12.html"
            report.write_text(report.read_text() + "Altered content")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                backfill_reports(manifest_path=root / "backfill" / "manifest.json", site_dir=root / "site", seen_path=root / "seen.json")
            self.assertFalse((root / "site").exists())


if __name__ == "__main__":
    unittest.main()
