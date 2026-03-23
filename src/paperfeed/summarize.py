from __future__ import annotations

import json
import re
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from paperfeed.models import DigestEntry, LlamaCppConfig, Paper, PaperSummary, SummarizerConfig

STOPWORDS = {
    "about",
    "after",
    "among",
    "and",
    "between",
    "from",
    "into",
    "paper",
    "study",
    "their",
    "these",
    "this",
    "using",
    "with",
}

METHOD_HINTS = ("method", "approach", "framework", "model", "algorithm", "benchmark", "dataset")
RESULT_HINTS = ("result", "show", "demonstrate", "improve", "outperform", "achieve", "find")
SUMMARY_KEYS = (
    "why_it_matters",
    "main_idea",
    "method",
    "key_results",
    "limitations",
    "relevance_to_my_research",
)


class PaperSummarizer(Protocol):
    def summarize_paper(self, paper: Paper, seed_papers: list[Paper]) -> PaperSummary:
        """Build a structured summary for one paper."""


def create_summarizer(config: SummarizerConfig | None = None) -> PaperSummarizer:
    active_config = config or SummarizerConfig()
    if active_config.backend == "deterministic":
        return DeterministicSummarizer()
    if active_config.backend == "llama-cpp":
        return LlamaCppSummarizer(active_config.llama_cpp)
    raise ValueError(f"Unsupported summarizer backend: {active_config.backend}")


def build_digest_entries(
    papers: list[Paper],
    seed_papers: list[Paper],
    *,
    summarizer: PaperSummarizer | None = None,
) -> list[DigestEntry]:
    active_summarizer = summarizer or DeterministicSummarizer()
    return [
        DigestEntry(
            paper=paper,
            summary=active_summarizer.summarize_paper(paper, seed_papers),
            matched_seed_titles=match_seed_titles(paper, seed_papers),
        )
        for paper in papers
    ]


def summarize_paper(
    paper: Paper,
    seed_papers: list[Paper],
    *,
    summarizer: PaperSummarizer | None = None,
) -> PaperSummary:
    active_summarizer = summarizer or DeterministicSummarizer()
    return active_summarizer.summarize_paper(paper, seed_papers)


class DeterministicSummarizer:
    def summarize_paper(self, paper: Paper, seed_papers: list[Paper]) -> PaperSummary:
        matched_seed_titles = match_seed_titles(paper, seed_papers)
        abstract_sentences = split_sentences(paper.abstract or "")
        first_sentence = abstract_sentences[0] if abstract_sentences else None

        why_it_matters_parts = []
        if matched_seed_titles:
            why_it_matters_parts.append(
                f"Semantic Scholar linked it to seeds such as {format_title_list(matched_seed_titles)}."
            )
        else:
            why_it_matters_parts.append("Semantic Scholar surfaced it from the current seed set.")
        if paper.year:
            why_it_matters_parts.append(f"Publication year: {paper.year}.")
        if paper.citation_count is not None:
            why_it_matters_parts.append(f"Citations: {paper.citation_count}.")

        main_idea = first_sentence or f"The title suggests a focus on {paper.title}."
        method = (
            choose_sentence(abstract_sentences, METHOD_HINTS)
            or "The abstract does not expose enough detail to state the method confidently."
        )
        key_results = (
            choose_sentence(abstract_sentences, RESULT_HINTS, exclude=method)
            or "The abstract does not report enough concrete results to summarize them reliably."
        )
        limitations = (
            "This summary is based on the abstract only; implementation details, evaluation setup, and failure modes may be missing."
            if paper.abstract
            else "No abstract was available, so this entry is based on title and metadata only."
        )

        if matched_seed_titles:
            relevance = (
                f"The strongest title overlap is with {format_title_list(matched_seed_titles)}. "
                "Review whether the shared problem setting or method matches your current work."
            )
        else:
            relevance = (
                "Semantic Scholar surfaced it from the current seed set, but lexical overlap with the seed titles is weak. "
                "Review relevance manually."
            )

        return PaperSummary(
            basis="abstract-only",
            why_it_matters=" ".join(why_it_matters_parts),
            main_idea=main_idea,
            method=method,
            key_results=key_results,
            limitations=limitations,
            relevance_to_my_research=relevance,
        )


class LlamaCppSummarizer:
    def __init__(self, config: LlamaCppConfig) -> None:
        self._config = config

    def summarize_paper(self, paper: Paper, seed_papers: list[Paper]) -> PaperSummary:
        matched_seed_titles = match_seed_titles(paper, seed_papers)
        payload = {
            "model": self._config.model,
            "temperature": self._config.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You write concise technical summaries for a daily research digest. "
                        "Use only the provided title, metadata, abstract, and seed matches. "
                        "Do not claim to have read the full paper. "
                        "Return a JSON object and nothing else."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_llama_prompt(paper, matched_seed_titles),
                },
            ],
        }
        response_text = self._post_chat_completion(payload)
        summary_data = _parse_summary_json(response_text)

        return PaperSummary(
            basis="abstract-only",
            why_it_matters=_require_summary_field(summary_data, "why_it_matters"),
            main_idea=_require_summary_field(summary_data, "main_idea"),
            method=_require_summary_field(summary_data, "method"),
            key_results=_require_summary_field(summary_data, "key_results"),
            limitations=_require_summary_field(summary_data, "limitations"),
            relevance_to_my_research=_require_summary_field(
                summary_data,
                "relevance_to_my_research",
            ),
        )

    def _post_chat_completion(self, payload: dict[str, object]) -> str:
        endpoint = f"{self._config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        request = Request(
            url=endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._config.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"llama.cpp request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Failed to reach the llama.cpp server at {endpoint}."
            ) from exc

        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("llama.cpp response did not contain any choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("llama.cpp response choice payload must be an object.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("llama.cpp response did not contain a message payload.")

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
            if text_parts:
                return "\n".join(text_parts)

        raise RuntimeError("llama.cpp response did not contain textual message content.")


def match_seed_titles(paper: Paper, seed_papers: list[Paper], limit: int = 2) -> list[str]:
    target_tokens = token_set(" ".join(part for part in [paper.title, paper.abstract or ""] if part))
    scored = []
    for seed in seed_papers:
        seed_tokens = token_set(seed.title)
        overlap = len(target_tokens & seed_tokens)
        scored.append((overlap, seed.title))

    scored.sort(key=lambda item: (-item[0], item[1].lower()))
    return [title for score, title in scored if score > 0][:limit]


def split_sentences(text: str) -> list[str]:
    if not text.strip():
        return []
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [sentence.strip() for sentence in raw_sentences if sentence.strip()]


def choose_sentence(
    sentences: list[str],
    keywords: tuple[str, ...],
    *,
    exclude: str | None = None,
) -> str | None:
    exclude_text = (exclude or "").strip()
    for sentence in sentences:
        normalized = sentence.lower()
        if exclude_text and sentence == exclude_text:
            continue
        if any(keyword in normalized for keyword in keywords):
            return sentence
    for sentence in sentences[1:]:
        if exclude_text and sentence == exclude_text:
            continue
        return sentence
    return None


def token_set(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {token for token in tokens if len(token) > 3 and token not in STOPWORDS}


def format_title_list(titles: list[str]) -> str:
    if not titles:
        return "the current seed set"
    if len(titles) == 1:
        return f"'{titles[0]}'"
    return ", ".join(f"'{title}'" for title in titles[:-1]) + f" and '{titles[-1]}'"


def _build_llama_prompt(paper: Paper, matched_seed_titles: list[str]) -> str:
    matched_seed_block = ", ".join(matched_seed_titles) if matched_seed_titles else "None"
    field_list = "\n".join(f"- {key}" for key in SUMMARY_KEYS)
    return f"""
Summarize the following paper for a small daily research digest.

Return valid JSON with exactly these string keys:
{field_list}

Rules:
- Base every statement only on the provided metadata and abstract.
- Do not imply access to the full text.
- Mention uncertainty when the abstract is incomplete.
- Keep each field concise, specific, and technical.

Paper title: {paper.title}
Authors: {", ".join(author.name for author in paper.authors) or "Unknown authors"}
Venue: {paper.venue or "Unknown venue"}
Year: {paper.year or "Unknown year"}
Citation count: {paper.citation_count if paper.citation_count is not None else "Unknown"}
Matched seed titles: {matched_seed_block}
Abstract:
{paper.abstract or "No abstract available."}
""".strip()


def _parse_summary_json(text: str) -> dict[str, object]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("llama.cpp did not return a JSON object.")

    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError("llama.cpp returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("llama.cpp JSON payload must be an object.")
    return payload


def _require_summary_field(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"llama.cpp summary is missing a non-empty '{key}' field.")
    return value.strip()
