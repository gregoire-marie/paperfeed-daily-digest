"""Rebuild verified historical report transcriptions without consulting an LLM."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import date
import hashlib
import json
from pathlib import Path

from paperfeed.dedup import SeenStore, title_hash_for_title
from paperfeed.models import SeenPaper
from paperfeed.site_builder import build_index_page, build_transcribed_digest_page


@dataclass(frozen=True, slots=True)
class TranscribedReport:
    """A checked, unchanged report body and its chosen archive date."""

    report_date: date
    html: str
    titles: tuple[str, ...]
    item_count: int
    existing_html: str = ""


def load_reports(manifest_path: Path) -> list[TranscribedReport]:
    """Read canonical report bodies and reject missing or modified transcriptions."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reports: list[TranscribedReport] = []
    for item in manifest["reports"]:
        report_date = date.fromisoformat(item["date"])
        stem = manifest_path.parent / "reports" / report_date.isoformat()
        html = stem.with_suffix(".html").read_text(encoding="utf-8")
        text = stem.with_suffix(".txt").read_text(encoding="utf-8")
        for content, expected in ((html, item["html_sha256"]), (text, item["text_sha256"])):
            if hashlib.sha256(content.encode("utf-8")).hexdigest() != expected:
                raise ValueError(f"Transcription checksum mismatch for {report_date}.")
        if item["source_character_count"] != item["accounted_character_count"]:
            raise ValueError(f"Incomplete source-character audit for {report_date}.")
        existing_html = ""
        if "repo_html_sha256" in item:
            extra_path = manifest_path.parent / "reports" / f"{report_date.isoformat()}-repo.html"
            existing_html = extra_path.read_text(encoding="utf-8")
            if hashlib.sha256(existing_html.encode("utf-8")).hexdigest() != item["repo_html_sha256"]:
                raise ValueError(f"Existing repository report checksum mismatch for {report_date}.")
        reports.append(TranscribedReport(report_date, html, tuple(item["titles"]), item["item_count"], existing_html))
    if len({report.report_date for report in reports}) != len(reports):
        raise ValueError("Transcribed report dates must be unique.")
    return sorted(reports, key=lambda report: report.report_date)


def backfill_reports(
    *, manifest_path: Path = Path("data/backfill/manifest.json"),
    site_dir: Path = Path("site"), seen_path: Path = Path("data/seen.json"),
) -> list[Path]:
    """Publish every canonical transcription and remember its original item titles.

    Args:
        manifest_path: Audit manifest for the preserved report bodies.
        site_dir: Static site output directory.
        seen_path: Existing deduplication state, which is preserved and extended.

    Returns:
        The chronological list of generated report paths.
    """
    reports = load_reports(manifest_path)
    store = SeenStore.load(seen_path)
    indices = {record.title_hash: index for index, record in enumerate(store.papers)}
    paths: list[Path] = []
    for report in reports:
        extra = report.existing_html
        content = extra + "\n<!-- preserved-transcription -->\n" + report.html + "<!-- end-preserved-transcription -->\n"
        item_count = report.item_count + extra.count('<article class="panel paper-card')
        path = site_dir / "digests" / f"{report.report_date.isoformat()}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(build_transcribed_digest_page(report.report_date, content, item_count), encoding="utf-8")
        paths.append(path)
        for title in report.titles:
            title_hash = title_hash_for_title(title)
            day = report.report_date.isoformat()
            index = indices.get(title_hash)
            if index is None:
                indices[title_hash] = len(store.papers)
                store.papers.append(SeenPaper(title_hash=title_hash, first_seen_date=day, last_summarized_date=day))
            else:
                current = store.papers[index]
                store.papers[index] = replace(
                    current, first_seen_date=min(current.first_seen_date or day, day),
                    last_summarized_date=max(current.last_summarized_date or day, day),
                )
    store.save()
    (site_dir / "index.html").write_text(build_index_page(site_dir), encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> int:
    """Rebuild the archive from its checked source transcriptions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/backfill/manifest.json"))
    parser.add_argument("--site-dir", type=Path, default=Path("site"))
    parser.add_argument("--seen-file", type=Path, default=Path("data/seen.json"))
    args = parser.parse_args(argv)
    paths = backfill_reports(manifest_path=args.manifest, site_dir=args.site_dir, seen_path=args.seen_file)
    print(f"Rebuilt {len(paths)} preserved historical reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
