"""Check Semantic Scholar access locally without generating a digest."""

from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path
import sys

from paperfeed.config import load_config
from paperfeed.models import PaperSeed
from paperfeed.semantic_scholar import (
    SeedResolutionError,
    SemanticScholarClient,
    SemanticScholarError,
)

# The example paper from Semantic Scholar's API tutorial, independent of our seeds.
EXAMPLE_PAPER_ID = "649def34f8be52c8b66281af98ae884c09aef38b"


def main(argv: list[str] | None = None) -> int:
    """Prompt for an API key and test read-only Semantic Scholar requests.

    Args:
        argv: Optional CLI arguments; defaults to the process arguments.

    Returns:
        Zero on success, or one for an input or API error.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Also test seed resolution and recommendations using this seeds.yaml file.",
    )
    args = parser.parse_args(argv)
    api_key = ""
    try:
        api_key = _read_api_key()
        client = SemanticScholarClient(api_key=api_key)
        print("Checking a known paper with the supplied key (429 responses may take time to retry)...", flush=True)
        paper = client.resolve_seed(PaperSeed(paper_id=EXAMPLE_PAPER_ID))
        print(f"Paper lookup succeeded: {paper.title}")
        if args.config is not None:
            _check_configured_discovery(client, args.config, api_key)
    except (SemanticScholarError, ValueError, OSError, EOFError) as exc:
        print(f"Check failed: {_safe_message(exc, api_key)}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCheck cancelled.", file=sys.stderr)
        return 1

    print("API access works from this computer with the supplied key.")
    print("Public endpoints can also work without authentication; success alone does not prove the key was accepted.")
    return 0


def _read_api_key() -> str:
    if not sys.stdin.isatty():
        raise ValueError("Run this command in an interactive terminal so the key can be entered without echoing.")
    api_key = getpass("Paste your S2 API key (hidden): ").strip()
    if not api_key:
        raise ValueError("The API key must not be empty.")
    if any(char.isspace() for char in api_key) or api_key.startswith(("'", '"')):
        raise ValueError("Paste only the key value, without quotes or the email label.")
    return api_key


def _check_configured_discovery(client: SemanticScholarClient, config_path: Path, api_key: str) -> None:
    config = load_config(config_path)
    positive_ids: list[str] = []
    negative_ids: list[str] = []
    for role, seeds, resolved_ids in (
        ("positive", config.positive_seeds, positive_ids),
        ("negative", config.negative_seeds, negative_ids),
    ):
        for seed in seeds:
            try:
                paper = client.resolve_seed(seed)
            except SeedResolutionError as exc:
                print(f"Skipping unresolved {role} seed: {_safe_message(exc, api_key)}")
                continue
            resolved_ids.append(paper.paper_id)
            print(f"Resolved {role} seed: {paper.title}")
    if not positive_ids:
        raise ValueError("API access succeeded, but none of the positive seed identifiers could be resolved.")
    candidates = client.get_recommendations(positive_ids, negative_ids, limit=1)
    print(f"Recommendations request succeeded: {len(candidates)} candidate(s).")


def _safe_message(error: Exception, api_key: str) -> str:
    message = str(error)
    return message.replace(api_key, "[redacted]") if api_key else message


if __name__ == "__main__":
    raise SystemExit(main())
