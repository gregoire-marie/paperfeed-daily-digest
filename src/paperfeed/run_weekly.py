from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from paperfeed.config import load_config, load_summarizer_config
from paperfeed.dedup import SeenStore, filter_unseen_papers
from paperfeed.models import Digest, Paper, PaperFeedConfig, PaperSeed
from paperfeed.semantic_scholar import (
    DiscoveryClient,
    SeedResolutionError,
    SemanticScholarClient,
)
from paperfeed.site_builder import write_digest_site
from paperfeed.summarize import PaperSummarizer, build_digest_entries, create_summarizer

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WeeklyRunResult:
    digest: Digest
    resolved_positive_seeds: list[Paper]
    resolved_negative_seeds: list[Paper]
    candidate_count: int
    unseen_count: int
    selected_count: int
    digest_path: Path


class NoUsablePositiveSeedsError(RuntimeError):
    """Raised when none of the configured positive seeds resolve in Semantic Scholar."""


class DigestAlreadyExistsError(RuntimeError):
    """Raised when a weekly report already exists and must be preserved."""


def weekly_digest_date(today: date) -> date:
    """Return the most recent Sunday, keeping manual runs within one weekly slot."""
    return today - timedelta(days=(today.weekday() + 1) % 7)


def run_weekly(
    *,
    config_path: str | Path = "seeds.yaml",
    seen_path: str | Path = "data/seen.json",
    site_dir: str | Path = "site",
    top_k: int | None = None,
    digest_date: date | None = None,
    client: DiscoveryClient | None = None,
    summarizer: PaperSummarizer | None = None,
) -> WeeklyRunResult:
    """Retrieve, select, summarize, and publish a digest with discovery diagnostics."""
    run_date = digest_date or weekly_digest_date(date.today())
    existing_path = Path(site_dir) / "digests" / f"{run_date.isoformat()}.html"
    if existing_path.exists():
        raise DigestAlreadyExistsError(f"Weekly digest already exists at {existing_path}; preserving its content.")
    config = load_config(config_path)
    config = _apply_top_k_override(config, top_k)
    LOGGER.info(
        "event=seeds_loaded positive=%d negative=%d",
        len(config.positive_seeds), len(config.negative_seeds),
    )

    discovery_client = client or SemanticScholarClient()
    resolved_positive_seeds = _resolve_seeds(
        seeds=config.positive_seeds,
        discovery_client=discovery_client,
        role="positive",
    )
    resolved_negative_seeds = _resolve_seeds(
        seeds=config.negative_seeds,
        discovery_client=discovery_client,
        role="negative",
    )

    candidate_limit = min(
        500,
        config.preferences.max_candidates_per_seed * max(len(resolved_positive_seeds), 1),
    )
    candidates = discovery_client.get_recommendations(
        positive_paper_ids=[paper.paper_id for paper in resolved_positive_seeds],
        negative_paper_ids=[paper.paper_id for paper in resolved_negative_seeds],
        limit=candidate_limit,
    )
    filtered_candidates = _filter_candidates(candidates, config)

    seen_store = SeenStore.load(seen_path)
    unseen_candidates = filter_unseen_papers(filtered_candidates, seen_store)
    selected_papers = unseen_candidates[: config.preferences.top_k]
    filtered_count = len(candidates) - len(filtered_candidates)
    duplicate_count = len(filtered_candidates) - len(unseen_candidates)
    LOGGER.info(
        "event=candidates_selected retrieved=%d date_filtered=%d duplicates_removed=%d selected=%d",
        len(candidates), filtered_count, duplicate_count, len(selected_papers),
    )

    digest = Digest(
        digest_date=run_date,
        entries=build_digest_entries(
            selected_papers,
            resolved_positive_seeds,
            summarizer=summarizer,
        ),
        empty_reason=_empty_digest_reason(
            candidate_count=len(candidates),
            filtered_count=filtered_count,
            duplicate_count=duplicate_count,
            selected_count=len(selected_papers),
            min_publication_year=config.preferences.min_publication_year,
        ),
    )
    LOGGER.info("event=summaries_generated count=%d", len(digest.entries))
    if digest.empty_reason:
        LOGGER.info("event=empty_digest reason=%s", digest.empty_reason)
    digest_path = write_digest_site(digest, site_dir)
    previous_seen = seen_store.path.read_text(encoding="utf-8") if seen_store.path.exists() else None
    seen_store.mark_summarized(selected_papers, run_date.isoformat())
    seen_store.save()
    seen_changed = previous_seen != seen_store.path.read_text(encoding="utf-8")
    LOGGER.info("event=output_written path=%s seen_changed=%s", digest_path, seen_changed)

    return WeeklyRunResult(
        digest=digest,
        resolved_positive_seeds=resolved_positive_seeds,
        resolved_negative_seeds=resolved_negative_seeds,
        candidate_count=len(candidates),
        unseen_count=len(unseen_candidates),
        selected_count=len(selected_papers),
        digest_path=digest_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the weekly PaperFeed digest pipeline.")
    parser.add_argument("--config", default="seeds.yaml", help="Path to the seeds.yaml file.")
    parser.add_argument("--seen-file", default="data/seen.json", help="Path to the seen.json state file.")
    parser.add_argument("--site-dir", default="site", help="Directory where static files are written.")
    parser.add_argument("--top-k", type=int, default=None, help="Override preferences.top_k for this run.")
    parser.add_argument(
        "--summary-backend",
        choices=["deterministic", "llama-cpp"],
        default=None,
        help="Summarizer backend. Defaults to PAPERFEED_SUMMARIZER_BACKEND or deterministic.",
    )
    parser.add_argument(
        "--llama-base-url",
        default=None,
        help="Base URL for a llama.cpp OpenAI-compatible server.",
    )
    parser.add_argument(
        "--llama-model",
        default=None,
        help="Model identifier to send to the llama.cpp server.",
    )
    parser.add_argument(
        "--llama-api-key",
        default=None,
        help="Optional API key for the llama.cpp server.",
    )
    parser.add_argument(
        "--llama-temperature",
        type=float,
        default=None,
        help="Sampling temperature for llama.cpp summarization.",
    )
    parser.add_argument(
        "--llama-timeout-seconds",
        type=float,
        default=None,
        help="Timeout for llama.cpp summarization requests.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Digest date in ISO format (YYYY-MM-DD). Defaults to the most recent Sunday.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the weekly CLI, preserving existing reports on repeated execution."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    run_date = date.fromisoformat(args.date) if args.date else None
    summarizer_config = load_summarizer_config(
        backend=args.summary_backend,
        llama_base_url=args.llama_base_url,
        llama_model=args.llama_model,
        llama_api_key=args.llama_api_key,
        llama_temperature=args.llama_temperature,
        llama_timeout_seconds=args.llama_timeout_seconds,
    )

    try:
        result = run_weekly(
            config_path=args.config,
            seen_path=args.seen_file,
            site_dir=args.site_dir,
            top_k=args.top_k,
            digest_date=run_date,
            summarizer=create_summarizer(summarizer_config),
        )
    except DigestAlreadyExistsError as exc:
        LOGGER.info("event=weekly_digest_preserved reason=%s", exc)
        return 0

    print(
        f"Generated digest for {result.digest.digest_date.isoformat()} at {result.digest_path} "
        f"({result.selected_count} selected from {result.candidate_count} candidates, {result.unseen_count} unseen)."
    )
    return 0


def _apply_top_k_override(config: PaperFeedConfig, top_k: int | None) -> PaperFeedConfig:
    if top_k is None:
        return config
    if top_k <= 0:
        raise ValueError("--top-k must be greater than zero.")
    return PaperFeedConfig(
        positive_seeds=config.positive_seeds,
        negative_seeds=config.negative_seeds,
        preferences=replace(config.preferences, top_k=top_k),
    )


def _filter_candidates(candidates: list[Paper], config: PaperFeedConfig) -> list[Paper]:
    min_year = config.preferences.min_publication_year
    if min_year is None:
        return candidates
    return [paper for paper in candidates if (paper.year or 0) >= min_year]


def _resolve_seeds(
    *,
    seeds: list[PaperSeed],
    discovery_client: DiscoveryClient,
    role: str,
) -> list[Paper]:
    resolved: list[Paper] = []
    unresolved: list[PaperSeed] = []

    for seed in seeds:
        try:
            paper = discovery_client.resolve_seed(seed)
            resolved.append(paper)
            LOGGER.info(
                "event=seed_resolved role=%s identifier=%s paper_id=%s title=%s",
                role, seed.identifier, paper.paper_id, paper.title,
            )
        except SeedResolutionError as exc:
            unresolved.append(seed)
            LOGGER.warning("Skipping %s seed '%s': %s", role, seed.identifier, exc)

    if role == "positive" and not resolved:
        unresolved_labels = ", ".join(_describe_seed(seed) for seed in unresolved) or "none"
        raise NoUsablePositiveSeedsError(
            "None of the configured positive seeds could be resolved in Semantic Scholar. "
            f"Unresolved seeds: {unresolved_labels}. "
            "A DOI lookup can fail even if the paper is indexed under a Semantic Scholar paper_id. "
            "Use a Semantic Scholar paper_id or another indexed seed."
        )

    return resolved


def _describe_seed(seed: PaperSeed) -> str:
    return f"{seed.identifier_kind}={seed.identifier}"


def _empty_digest_reason(
    *, candidate_count: int, filtered_count: int, duplicate_count: int,
    selected_count: int, min_publication_year: int | None,
) -> str | None:
    if selected_count:
        return None
    if candidate_count == 0:
        return "Semantic Scholar returned no recommendations for the resolved seed papers."
    noun = "recommendation" if candidate_count == 1 else "recommendations"
    reasons = [f"Semantic Scholar returned {candidate_count} {noun}."]
    if filtered_count:
        reasons.append(
            f"{filtered_count} {'was' if filtered_count == 1 else 'were'} excluded by the publication-year filter: "
            f"papers must be from {min_publication_year} or later; papers with no publication year are also excluded."
        )
    if duplicate_count:
        noun = "paper" if duplicate_count == 1 else "papers"
        reasons.append(f"{duplicate_count} eligible {noun} had already appeared in previous digests.")
    return " ".join(reasons)


if __name__ == "__main__":
    raise SystemExit(main())
