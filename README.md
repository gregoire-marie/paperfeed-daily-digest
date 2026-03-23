# PaperFeed

PaperFeed is a minimal daily research digest for researchers who want a small, high-signal paper feed instead of infinite social media scrolling.

It is designed for one job:

1. start from a small set of seed papers that represent your research,
2. fetch new related papers every day,
3. summarize the best ones with a fixed structure,
4. publish a simple static digest page to GitHub Pages.

The project intentionally avoids complexity.

## Goals

- Discover papers similar to your own papers.
- Run automatically every day.
- Avoid repeating papers that were already shown.
- Produce concise, structured summaries.
- Publish a mobile-friendly static digest you can read from your iPhone all day.

## Non-goals

PaperFeed does **not** try to:

- scrape ResearchGate,
- reproduce ResearchGate ranking exactly,
- build a full research search engine,
- host every PDF forever,
- add vector databases, embeddings infrastructure, or multi-stage retrieval unless explicitly needed,
- turn the GitHub Pages site into a complex app.

## Project philosophy

PaperFeed stays deliberately small:

- **one discovery source**: Semantic Scholar recommendations,
- **one memory file**: `data/seen.json`,
- **one main runner**: `python -m paperfeed.run_daily`,
- **one static output**: a daily digest page in `site/`.

The site is a reading surface, not a platform.

## How it works

### 1. Seed papers

You provide a small set of seed papers that define your interests.

Typical seed papers include:

- your own papers,
- papers you cite often,
- papers very close to your current research direction.

Optional negative seeds can be used later to push the recommendations away from nearby but irrelevant topics.

### 2. Candidate discovery

PaperFeed queries Semantic Scholar recommendations from those seeds and retrieves candidate papers related to them.

### 3. Deduplication

Candidates already present in `data/seen.json` are discarded.

Deduplication is based on the best identifier available, in this priority order:

1. DOI,
2. Semantic Scholar `paperId`,
3. normalized title hash.

### 4. Selection

The daily runner keeps the top `k` unseen candidates after lightweight filtering.

The first version should remain simple. Avoid adding sophisticated reranking unless there is a demonstrated quality problem.

### 5. Summarization

For each selected paper, PaperFeed produces a summary with the same sections every time.

Default structure:

1. Why it matters
2. Main idea
3. Method
4. Key results
5. Limitations
6. Relevance to my research

Each summary must also include a clear basis field:

- `basis: full-text`
- `basis: abstract-only`

This prevents false confidence when the PDF is unavailable or not parsed.

### 6. Publishing

PaperFeed writes static HTML or Markdown pages under `site/`.

The homepage links to the latest digest pages. Each paper entry contains:

- title,
- authors,
- venue or source when available,
- publication date when available,
- summary,
- external PDF link when available,
- external source link.

## What gets published

PaperFeed publishes summaries and links.

By default, it should **not** store or republish a permanent copy of every PDF in the repository.

Recommended behavior:

- keep summaries in the repository,
- keep external links to PDFs and source pages,
- optionally cache PDFs locally outside Git for transient processing,
- only publish a PDF file directly if you have explicitly decided to do so.

## Repository layout

A minimal target layout is:

```text
paperfeed-daily-digest/
├─ README.md
├─ AGENTS.md
├─ pyproject.toml
├─ seeds.yaml
├─ data/
│  └─ seen.json
├─ site/
│  ├─ index.html
│  └─ digests/
├─ src/
│  └─ paperfeed/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ models.py
│     ├─ semantic_scholar.py
│     ├─ dedup.py
│     ├─ summarize.py
│     ├─ site_builder.py
│     └─ run_daily.py
└─ .github/
   └─ workflows/
      └─ daily.yml
```

## Configuration

## `seeds.yaml`

This file defines the papers that shape your digest.

Example:

```yaml
positive_seeds:
  - doi: "10.48550/arXiv.2401.12345"
  - doi: "10.2514/1.A35555"
  - paper_id: "0123456789abcdef0123456789abcdef01234567"

negative_seeds: []

preferences:
  top_k: 5
  max_candidates_per_seed: 20
  min_publication_year: 2023
```

Keep the seed set small and high quality. A few excellent seeds are better than a large noisy list.
When you use a DOI seed, that paper still needs to exist in Semantic Scholar's index. A DOI
that resolves at `doi.org` can still be missing from Semantic Scholar; in that case, use the
Semantic Scholar `paper_id` for that paper or replace the seed with another indexed paper.

## `data/seen.json`

This file records papers that were already shown.

Example:

```json
{
  "papers": [
    {
      "paper_id": "abcdef1234567890",
      "doi": "10.48550/arXiv.2501.01234",
      "title_hash": "6a9d7f...",
      "first_seen_date": "2026-03-23",
      "last_summarized_date": "2026-03-23"
    }
  ]
}
```

Do not store more state than necessary in the first version.

## Installation

## Requirements

- Python 3.11+
- a GitHub repository named `paperfeed-daily-digest`
- GitHub Pages enabled for the repository
- optionally, a Semantic Scholar API key if you choose to use one
- optionally, a local `llama.cpp` server for LLM-based summarization

## Local setup

```bash
git clone git@github.com:<your-user>/paperfeed-daily-digest.git
cd paperfeed-daily-digest
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Environment variables

Example:

```bash
export S2_API_KEY="..."
```

Use only the variables you actually need.

PaperFeed does not require an OpenAI API key.

The default summarizer is deterministic and works without any LLM service. To use a local
`llama.cpp` model instead, start `llama-server` and set:

```bash
export PAPERFEED_SUMMARIZER_BACKEND="llama-cpp"
export LLAMA_CPP_BASE_URL="http://127.0.0.1:8080/v1"
export LLAMA_CPP_MODEL="local-model"
```

If your `llama.cpp` server is protected with `--api-key`, you can also set:

```bash
export LLAMA_CPP_API_KEY="..."
```

## Running locally

Run the full daily pipeline:

```bash
python -m paperfeed.run_daily --top-k 5
```

Run it against a local `llama.cpp` server:

```bash
python -m paperfeed.run_daily \
  --summary-backend llama-cpp \
  --llama-base-url http://127.0.0.1:8080/v1 \
  --llama-model local-model
```

Typical effects of one run:

- fetch recommendations,
- remove already seen papers,
- summarize the selected papers,
- write a new daily digest page,
- refresh `site/index.html`,
- update `data/seen.json`.

## Expected output

After a successful run, you should get something like:

```text
site/
├─ index.html
└─ digests/
   ├─ 2026-03-23.html
   └─ 2026-03-24.html
```

Each daily page should be fully static and directly viewable in a browser.

## GitHub Pages deployment

PaperFeed is intended to publish a static project site.

Recommended approach:

- generate the static files into `site/`,
- publish them with GitHub Pages,
- keep the resulting site simple and mobile-friendly.

## GitHub Actions automation

A daily workflow should:

1. check out the repository,
2. install dependencies,
3. run `python -m paperfeed.run_daily`,
4. commit the updated `site/` and `data/seen.json` files if they changed,
5. publish the Pages site.

A minimal workflow usually also supports manual triggering for testing.

## Summary style contract

All summaries must follow the same structure and tone.

They should be:

- concise,
- technical,
- explicit about uncertainty,
- explicit about whether they rely on abstract only or full text,
- focused on decisions and research value.

They should **not** be:

- generic,
- promotional,
- padded with broad statements,
- written like a literature review section,
- written like social media.

## Relevance rule

Every paper entry must answer one question clearly:

**Why should this matter for my research?**

If that answer is weak, the paper should probably not be in the digest.

## Suggested first implementation scope

Version 1 should include only:

- Semantic Scholar recommendation retrieval,
- seed configuration,
- deduplication through `seen.json`,
- one default summarization backend with an optional local `llama.cpp` alternative,
- one static digest page per day,
- GitHub Actions daily automation.

Do not implement tags, filters, search, accounts, databases, dashboards, or analytics in version 1.

## Example user experience

A normal daily workflow is:

1. open the GitHub Pages site on iPhone,
2. read the latest daily digest,
3. open the external PDF links for the papers worth deeper reading,
4. come back the next day for a new small batch.

The product is meant to feel like a focused reading ritual, not a content stream.

## Development principles

When contributing to PaperFeed:

- prefer clarity over abstraction,
- prefer explicit data models over ad hoc dicts,
- prefer deterministic outputs,
- keep the site static,
- keep the state small,
- do not add features that make the reading experience more complicated.

## Roadmap

### Version 1

- seed papers
- candidate retrieval
- deduplication
- summarization
- static daily page generation
- GitHub Actions daily run

### Possible later additions

Only add these if a concrete need appears:

- lightweight recency filtering,
- negative seeds,
- better metadata normalization,
- local non-versioned PDF cache,
- email notification with the daily digest link.

## License

Choose the license you want for the repository code.

Common choices:

- MIT
- Apache-2.0

Do not assume rights to redistribute third-party PDFs.

## Status

This project is intentionally small by design.

If a proposed feature makes the system behave like a feed platform, search engine, document archive, or research management suite, it is probably out of scope.
