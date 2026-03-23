from __future__ import annotations

import json
import os
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from paperfeed.models import Paper, PaperAuthor, PaperSeed


class SemanticScholarError(RuntimeError):
    """Raised when the Semantic Scholar API request fails."""


class SemanticScholarNotFoundError(SemanticScholarError):
    """Raised when Semantic Scholar does not have a record for the requested resource."""

    def __init__(self, resource: str, details: str) -> None:
        self.resource = resource
        self.details = details
        super().__init__(f"Semantic Scholar resource not found for {resource}: {details}")


class SeedResolutionError(SemanticScholarError):
    """Raised when a configured seed cannot be resolved to a Semantic Scholar paper."""


class DiscoveryClient(Protocol):
    def resolve_seed(self, seed: PaperSeed) -> Paper:
        ...

    def get_recommendations(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str],
        limit: int,
    ) -> list[Paper]:
        ...


class SemanticScholarClient:
    GRAPH_BASE_URL = "https://api.semanticscholar.org/graph/v1"
    RECOMMENDATIONS_BASE_URL = "https://api.semanticscholar.org/recommendations/v1"
    PAPER_FIELDS = ",".join(
        [
            "paperId",
            "title",
            "abstract",
            "authors",
            "venue",
            "year",
            "publicationDate",
            "url",
            "openAccessPdf",
            "externalIds",
            "citationCount",
        ]
    )

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 30) -> None:
        self.api_key = api_key or os.getenv("S2_API_KEY")
        self.timeout_seconds = timeout_seconds

    def resolve_seed(self, seed: PaperSeed) -> Paper:
        identifier = seed.paper_id or f"DOI:{seed.doi}"
        encoded_identifier = quote(identifier, safe=":")
        try:
            payload = self._request_json(
                method="GET",
                url=f"{self.GRAPH_BASE_URL}/paper/{encoded_identifier}",
                params={"fields": self.PAPER_FIELDS},
            )
        except SemanticScholarNotFoundError as exc:
            raise SeedResolutionError(_build_seed_not_found_message(seed, exc.details)) from exc
        return _paper_from_api_payload(payload)

    def get_recommendations(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str],
        limit: int,
    ) -> list[Paper]:
        capped_limit = max(1, min(limit, 500))
        payload = self._request_json(
            method="POST",
            url=f"{self.RECOMMENDATIONS_BASE_URL}/papers",
            params={"fields": self.PAPER_FIELDS, "limit": str(capped_limit)},
            body={
                "positivePaperIds": positive_paper_ids,
                "negativePaperIds": negative_paper_ids,
            },
        )
        recommended = payload.get("recommendedPapers", [])
        return [_paper_from_api_payload(item) for item in recommended]

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        request_url = url
        if params:
            request_url = f"{request_url}?{urlencode(params)}"

        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        if self.api_key:
            headers["x-api-key"] = self.api_key

        request = Request(request_url, headers=headers, method=method, data=data)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404:
                raise SemanticScholarNotFoundError(request_url, details) from exc
            raise SemanticScholarError(
                f"Semantic Scholar request failed with HTTP {exc.code}: {details}"
            ) from exc
        except URLError as exc:
            raise SemanticScholarError(f"Semantic Scholar request failed: {exc.reason}") from exc


def _build_seed_not_found_message(seed: PaperSeed, details: str) -> str:
    if seed.doi:
        return (
            f"Configured DOI seed '{seed.doi}' could not be resolved in Semantic Scholar. "
            "The DOI may exist at doi.org without being indexed by Semantic Scholar yet. "
            f"API response: {details}"
        )
    return (
        f"Configured paper_id seed '{seed.paper_id}' could not be found in Semantic Scholar. "
        f"API response: {details}"
    )


def _paper_from_api_payload(payload: dict[str, object]) -> Paper:
    external_ids = payload.get("externalIds") or {}
    if not isinstance(external_ids, dict):
        external_ids = {}
    open_access_pdf = payload.get("openAccessPdf") or {}
    if not isinstance(open_access_pdf, dict):
        open_access_pdf = {}

    authors_payload = payload.get("authors") or []
    authors = []
    if isinstance(authors_payload, list):
        for author in authors_payload:
            if not isinstance(author, dict):
                continue
            name = str(author.get("name") or "Unknown author")
            author_id = author.get("authorId")
            authors.append(PaperAuthor(name=name, author_id=str(author_id) if author_id else None))

    paper_id = str(payload.get("paperId") or "").strip()
    if not paper_id:
        raise SemanticScholarError("Semantic Scholar returned a paper payload without paperId.")

    publication_date = _maybe_clean_string(payload.get("publicationDate"))
    year = payload.get("year")
    if not isinstance(year, int) and publication_date:
        year = _year_from_publication_date(publication_date)

    return Paper(
        paper_id=paper_id,
        title=str(payload.get("title") or "Untitled paper").strip(),
        abstract=_maybe_clean_string(payload.get("abstract")),
        authors=authors,
        venue=_maybe_clean_string(payload.get("venue")),
        year=year if isinstance(year, int) else None,
        publication_date=publication_date,
        url=_maybe_clean_string(payload.get("url")),
        pdf_url=_maybe_clean_string(open_access_pdf.get("url")),
        doi=_maybe_clean_string(external_ids.get("DOI") or external_ids.get("doi")),
        citation_count=_parse_int(payload.get("citationCount")),
    )


def _parse_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _maybe_clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _year_from_publication_date(publication_date: str) -> int | None:
    year_text = publication_date[:4]
    if year_text.isdigit():
        return int(year_text)
    return None
