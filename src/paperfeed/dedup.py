from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from paperfeed.models import Paper, SeenPaper


def filter_unseen_papers(papers: list[Paper], seen_store: "SeenStore") -> list[Paper]:
    return [paper for paper in papers if not seen_store.is_seen(paper)]


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.lower())).strip()


def title_hash_for_paper(paper: Paper) -> str:
    normalized = normalize_title(paper.title)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class SeenStore:
    def __init__(self, path: str | Path, papers: list[SeenPaper] | None = None) -> None:
        self.path = Path(path)
        self.papers = papers or []

    @classmethod
    def load(cls, path: str | Path) -> "SeenStore":
        store_path = Path(path)
        if not store_path.exists():
            return cls(store_path, [])

        payload = json.loads(store_path.read_text(encoding="utf-8"))
        raw_papers = payload.get("papers", [])
        papers = []
        if isinstance(raw_papers, list):
            for item in raw_papers:
                if not isinstance(item, dict):
                    continue
                papers.append(
                    SeenPaper(
                        paper_id=_maybe_string(item.get("paper_id")),
                        doi=_normalize_doi(_maybe_string(item.get("doi"))),
                        title_hash=_maybe_string(item.get("title_hash")),
                        first_seen_date=_maybe_string(item.get("first_seen_date")),
                        last_summarized_date=_maybe_string(item.get("last_summarized_date")),
                    )
                )
        return cls(store_path, papers)

    def is_seen(self, paper: Paper) -> bool:
        return self._find_match_index(paper) is not None

    def mark_summarized(self, papers: list[Paper], summarized_on: str) -> None:
        for paper in papers:
            match_index = self._find_match_index(paper)
            if match_index is None:
                self.papers.append(
                    SeenPaper(
                        paper_id=paper.paper_id,
                        doi=_normalize_doi(paper.doi),
                        title_hash=title_hash_for_paper(paper),
                        first_seen_date=summarized_on,
                        last_summarized_date=summarized_on,
                    )
                )
                continue

            current = self.papers[match_index]
            self.papers[match_index] = SeenPaper(
                paper_id=current.paper_id or paper.paper_id,
                doi=current.doi or _normalize_doi(paper.doi),
                title_hash=current.title_hash or title_hash_for_paper(paper),
                first_seen_date=current.first_seen_date or summarized_on,
                last_summarized_date=summarized_on,
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "papers": [
                {key: value for key, value in asdict(record).items() if value is not None}
                for record in self.papers
            ]
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _find_match_index(self, paper: Paper) -> int | None:
        paper_doi = _normalize_doi(paper.doi)
        paper_title_hash = title_hash_for_paper(paper)

        for index, record in enumerate(self.papers):
            if paper_doi and record.doi == paper_doi:
                return index
            if record.paper_id and record.paper_id == paper.paper_id:
                return index
            if record.title_hash and record.title_hash == paper_title_hash:
                return index
        return None


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.strip().lower()


def _maybe_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
