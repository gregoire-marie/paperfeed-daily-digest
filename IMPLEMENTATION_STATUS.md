# Implementation Status

Updated: 2026-10-11

## Completed

- Weekly Sunday generation, manual triggering, and separate publishing on site pushes
- Protection of existing weekly pages on repeated runs
- Twelve original weekly ChatGPT briefings transcribed with source and date audits
- October 11 blend preserving the five original PaperFeed papers and five briefing items
- Standard-library archive rebuild, transcription checksums, and imported-title deduplication

- Project packaging and `src/paperfeed/` module layout
- Seed configuration loading from `seeds.yaml`
- Semantic Scholar seed resolution and recommendations client
- Deduplication using `data/seen.json`
- Deterministic abstract-based summaries with a fixed section contract
- Optional `llama.cpp` summarizer backend via a local OpenAI-compatible server
- Static digest page generation under `site/`
- Weekly runner CLI at `python -m paperfeed.run_weekly`
- GitHub Actions workflow for scheduled generation and Pages deployment
- Offline unit tests for config parsing, deduplication, and the weekly pipeline

## Pending

- Live API verification against Semantic Scholar from this environment
- Full-text retrieval and `basis: full-text` summaries
- Better reranking beyond API recommendation order
- Optional negative-seed tuning and PDF cache workflow
