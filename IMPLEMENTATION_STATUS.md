# Implementation Status

Updated: 2026-03-23

## Completed

- Project packaging and `src/paperfeed/` module layout
- Seed configuration loading from `seeds.yaml`
- Semantic Scholar seed resolution and recommendations client
- Deduplication using `data/seen.json`
- Deterministic abstract-based summaries with a fixed section contract
- Optional `llama.cpp` summarizer backend via a local OpenAI-compatible server
- Static digest page generation under `site/`
- Daily runner CLI at `python -m paperfeed.run_daily`
- GitHub Actions workflow for scheduled generation and Pages deployment
- Offline unit tests for config parsing, deduplication, and the daily pipeline

## Pending

- Live API verification against Semantic Scholar from this environment
- Full-text retrieval and `basis: full-text` summaries
- Better reranking beyond API recommendation order
- Optional negative-seed tuning and PDF cache workflow
