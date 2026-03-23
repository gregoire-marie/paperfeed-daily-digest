from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

SummaryBasis = Literal["full-text", "abstract-only"]
SummarizerBackend = Literal["deterministic", "llama-cpp"]


@dataclass(frozen=True, slots=True)
class PaperSeed:
    doi: str | None = None
    paper_id: str | None = None

    def __post_init__(self) -> None:
        normalized_doi = _normalize_seed_doi(self.doi)
        normalized_paper_id = _normalize_optional_string(self.paper_id)
        object.__setattr__(self, "doi", normalized_doi)
        object.__setattr__(self, "paper_id", normalized_paper_id)

        provided = [value for value in (normalized_doi, normalized_paper_id) if value]
        if len(provided) != 1:
            raise ValueError("Each seed must define exactly one of doi or paper_id.")

    @property
    def identifier(self) -> str:
        return self.doi or self.paper_id or ""

    @property
    def identifier_kind(self) -> str:
        return "doi" if self.doi else "paper_id"


@dataclass(frozen=True, slots=True)
class DigestPreferences:
    top_k: int = 5
    max_candidates_per_seed: int = 20
    min_publication_year: int | None = None

    def __post_init__(self) -> None:
        if self.top_k <= 0:
            raise ValueError("preferences.top_k must be greater than zero.")
        if self.max_candidates_per_seed <= 0:
            raise ValueError("preferences.max_candidates_per_seed must be greater than zero.")
        if self.min_publication_year is not None and self.min_publication_year < 1900:
            raise ValueError("preferences.min_publication_year looks invalid.")


@dataclass(frozen=True, slots=True)
class PaperFeedConfig:
    positive_seeds: list[PaperSeed]
    negative_seeds: list[PaperSeed] = field(default_factory=list)
    preferences: DigestPreferences = field(default_factory=DigestPreferences)

    def __post_init__(self) -> None:
        if not self.positive_seeds:
            raise ValueError("At least one positive seed is required.")


@dataclass(frozen=True, slots=True)
class LlamaCppConfig:
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "local-model"
    api_key: str | None = None
    temperature: float = 0.1
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("llama_cpp.base_url must be a non-empty string.")
        if not self.model:
            raise ValueError("llama_cpp.model must be a non-empty string.")
        if self.temperature < 0:
            raise ValueError("llama_cpp.temperature must be greater than or equal to zero.")
        if self.timeout_seconds <= 0:
            raise ValueError("llama_cpp.timeout_seconds must be greater than zero.")


@dataclass(frozen=True, slots=True)
class SummarizerConfig:
    backend: SummarizerBackend = "deterministic"
    llama_cpp: LlamaCppConfig = field(default_factory=LlamaCppConfig)

    def __post_init__(self) -> None:
        if self.backend not in {"deterministic", "llama-cpp"}:
            raise ValueError(
                "summarizer.backend must be one of: deterministic, llama-cpp."
            )


@dataclass(frozen=True, slots=True)
class PaperAuthor:
    name: str
    author_id: str | None = None


@dataclass(frozen=True, slots=True)
class Paper:
    paper_id: str
    title: str
    abstract: str | None = None
    authors: list[PaperAuthor] = field(default_factory=list)
    venue: str | None = None
    year: int | None = None
    publication_date: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    doi: str | None = None
    citation_count: int | None = None


@dataclass(frozen=True, slots=True)
class PaperSummary:
    basis: SummaryBasis
    why_it_matters: str
    main_idea: str
    method: str
    key_results: str
    limitations: str
    relevance_to_my_research: str


@dataclass(frozen=True, slots=True)
class DigestEntry:
    paper: Paper
    summary: PaperSummary
    matched_seed_titles: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Digest:
    digest_date: date
    entries: list[DigestEntry]


@dataclass(frozen=True, slots=True)
class SeenPaper:
    paper_id: str | None = None
    doi: str | None = None
    title_hash: str | None = None
    first_seen_date: str | None = None
    last_summarized_date: str | None = None


def _normalize_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_seed_doi(doi: str | None) -> str | None:
    cleaned = _normalize_optional_string(doi)
    if cleaned is None:
        return None

    lowered = cleaned.lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi.org/",
        "dx.doi.org/",
        "doi:",
    ):
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break

    normalized = cleaned.strip().lower()
    return normalized or None
