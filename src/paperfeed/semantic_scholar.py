from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from paperfeed.models import Paper, PaperAuthor, PaperSeed

LOGGER = logging.getLogger(__name__)


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
    """Retrieve papers sequentially within the shared Semantic Scholar rate limit.

    Use one client per daily run so Graph and Recommendations calls share pacing.
    """

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
        """Initialize the API client.

        Args:
            api_key: API key, falling back to the S2_API_KEY environment variable.
            timeout_seconds: Timeout for each HTTP request.
        """
        self.api_key = api_key or os.getenv("S2_API_KEY")
        self.timeout_seconds = timeout_seconds
        self._last_request_started: float | None = None

    def resolve_seed(self, seed: PaperSeed) -> Paper:
        """Resolve a configured DOI or paper ID to paper metadata."""
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
        """Retrieve related papers in API order from the configured seeds."""
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
        recommended = payload.get("recommendedPapers")
        if not isinstance(recommended, list) or any(not isinstance(item, dict) for item in recommended):
            raise SemanticScholarError(
                "Semantic Scholar recommendations response must contain a recommendedPapers array of paper objects."
            )
        LOGGER.info(
            "event=recommendations_received positive_ids=%s negative_ids=%s requested=%d returned=%d",
            ",".join(positive_paper_ids), ",".join(negative_paper_ids), capped_limit, len(recommended),
        )
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
        return self._send_with_retries(request)

    def _send_with_retries(self, request: Request) -> dict[str, object]:
        attempt = 1
        while True:
            self._wait_for_rate_limit()
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise SemanticScholarError("Semantic Scholar response must be a JSON object.")
                return payload
            except HTTPError as exc:
                with exc:
                    details = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < 5:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = _retry_delay(retry_after, attempt)
                    LOGGER.warning(
                        "Semantic Scholar HTTP 429; retrying in %.1f seconds (attempt %d/5).",
                        delay,
                        attempt + 1,
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue
                if exc.code == 404:
                    raise SemanticScholarNotFoundError(request.full_url, details) from exc
                advice = (
                    " After 5 attempts, the API is still rate-limiting this request. "
                    "Verify S2_API_KEY contains only the key value, check whether other "
                    "applications use the same key, and retry later."
                    if exc.code == 429
                    else ""
                )
                raise SemanticScholarError(
                    f"Semantic Scholar request failed with HTTP {exc.code}: {details}{advice}"
                ) from exc
            except URLError as exc:
                raise SemanticScholarError(f"Semantic Scholar request failed: {exc.reason}") from exc

    def _wait_for_rate_limit(self) -> None:
        # The 1 request/second allowance is cumulative across all endpoints.
        # Leave a small margin to avoid requests arriving at the boundary.
        if self._last_request_started is not None:
            remaining = 1.1 - (time.monotonic() - self._last_request_started)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_started = time.monotonic()


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    default_delay = float(5 * 2 ** (attempt - 1))
    if not retry_after:
        return default_delay
    value = retry_after.strip()
    if value.isascii() and value.isdigit():
        return max(default_delay, float(value))
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
        return max(default_delay, seconds)
    except (TypeError, ValueError, OverflowError):
        return default_delay


def _build_seed_not_found_message(seed: PaperSeed, details: str) -> str:
    if seed.doi:
        return (
            f"Configured DOI seed '{seed.doi}' could not be resolved in Semantic Scholar. "
            "The paper may still be indexed under its Semantic Scholar paper_id without a working DOI lookup. "
            "Use that paper_id when available. "
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
