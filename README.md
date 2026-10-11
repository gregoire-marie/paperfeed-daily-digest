# PaperFeed

PaperFeed is a minimal weekly research digest for researchers who want a small, high-signal paper feed instead of infinite social media scrolling.

It is designed for one job:

1. start from a small set of seed papers that represent your research,
2. fetch new related papers every week,
3. summarize the best ones with a fixed structure,
4. publish a simple static digest page to GitHub Pages.

The project intentionally avoids complexity.

## Goals

- Discover papers similar to your own papers.
- Run automatically every week.
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
- **one main runner**: `python -m paperfeed.run_weekly`,
- **one static output**: a weekly digest page in `site/`.

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

The weekly runner keeps the top `k` unseen candidates after lightweight filtering.

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
│     └─ run_weekly.py
└─ .github/
   └─ workflows/
      └─ weekly.yml
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
When you use a DOI seed, Semantic Scholar must be able to resolve that DOI to a paper.
A DOI can resolve at `doi.org` while its Semantic Scholar DOI lookup returns 404, even
when the paper has a Semantic Scholar page. Prefer the `paper_id` from the last segment
of that page's URL in this case. The two configured seeds use these IDs directly, with
their titles and DOIs kept as comments for readability.

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
- a Semantic Scholar API key stored as the `S2_API_KEY` repository secret for weekly automation
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

PaperFeed generates one report per week. Scheduled generation runs on Sundays at
06:17 UTC. A manual run uses the most recent Sunday as its default report date.
If that report already exists, the command exits successfully without changing
the report, fetching papers, or modifying deduplication state. This also protects
the historical transcriptions below.

The supported command is `python -m paperfeed.run_weekly` (or
`paperfeed-run-weekly`). The older `paperfeed.run_daily` / `paperfeed-run-daily`
commands remain compatibility aliases with the same weekly behavior.

### Check your Semantic Scholar key locally

From the repository directory, run this in an interactive terminal (Python 3.11+;
no installation or third-party dependencies required):

```bash
PYTHONPATH=src python3 -m paperfeed.check_s2
```

Paste the key value from your email at the hidden prompt. The command uses this
value directly rather than an existing `S2_API_KEY` environment variable. It does
not save the key, add it to shell history, or change `site/` or `data/seen.json`.
It tests a known indexed paper independently of your seeds, using the same client,
headers, pacing, and retries as the weekly pipeline.

To also test your seeds and a recommendations request:

```bash
PYTHONPATH=src python3 -m paperfeed.check_s2 --config seeds.yaml
```

A successful request shows that API access works from your computer with the
supplied key. These endpoints are public, so it does not independently prove the
key was accepted. HTTP 401/403 indicate an authentication or access problem; HTTP
429 indicates throttling and is not conclusive about key validity. HTTP 404 on a
configured seed means its identifier could not be resolved; a DOI lookup failure
does not prove the paper is absent from Semantic Scholar. If the local check works while CI
fails, compare the repository secret with the exact value you entered and start a
fresh workflow run on the latest `main` commit, rather than rerunning an old job.

Run the full weekly pipeline:

```bash
python -m paperfeed.run_weekly --top-k 5
```

Run it against a local `llama.cpp` server:

```bash
python -m paperfeed.run_weekly \
  --summary-backend llama-cpp \
  --llama-base-url http://127.0.0.1:8080/v1 \
  --llama-model local-model
```

Typical effects of one run:

- fetch recommendations,
- remove already seen papers,
- summarize the selected papers,
- write a new weekly digest page,
- refresh `site/index.html`,
- update `data/seen.json`.

## Expected output

After a successful run, you should get something like:

```text
site/
├─ index.html
└─ digests/
   ├─ 2026-10-11.html
   └─ 2026-10-18.html
```

Each weekly page should be fully static and directly viewable in a browser.

## GitHub Pages deployment

PaperFeed is intended to publish a static project site.

Recommended approach:

- generate the static files into `site/`,
- publish them with GitHub Pages,
- keep the resulting site simple and mobile-friendly.

## GitHub Actions automation

The workflow is `.github/workflows/weekly.yml`, named **Weekly Digest**. It supports
manual runs and one scheduled run per week. Pushes changing the site publish the
existing static content without generating another report. This lets historical
backfills deploy immediately while preserving the weekly generation cadence.

A weekly workflow should:

1. check out the repository,
2. install dependencies,
3. run `python -m paperfeed.run_weekly`,
4. commit the updated `site/` and `data/seen.json` files if they changed,
5. publish the Pages site.

A minimal workflow usually also supports manual triggering for testing.

### Enable unattended weekly reports

1. Open your repository's **Settings > Secrets and variables > Actions**.
2. Click **New repository secret**, name it `S2_API_KEY`, and paste only the key
   value from the Semantic Scholar email. The workflow already passes this secret
   to the process through its environment; do not put the key in source files.
3. In **Settings > Pages**, select **GitHub Actions** as the publishing source.
4. Open **Actions > Weekly Digest > Run workflow** to test a new run.

The weekly workflow uses a GitHub-hosted runner. It installs Python and PaperFeed,
retrieves recommendations, generates up to five summaries with the current seed
preferences, commits the generated pages and `data/seen.json`, and deploys the
static site. Your computer can be turned off. No Ollama or `llama.cpp` server is
required by the default summarizer.

The deterministic summarizer selects sentences from abstracts and adds fixed
context and limitations text; it does not use an LLM. Both current backends use
abstracts and metadata only, even when a PDF link is available. At least one
positive seed must be indexed by Semantic Scholar.

Semantic Scholar requests are spaced at least 1.1 seconds apart across both Graph
and Recommendations endpoints, respecting the key's cumulative one-request-per-second
limit. This pacing applies to a single client/run; other applications using the
same key share its allowance.

HTTP 429 responses are retried up to four times, with delays of 5, 10, 20, and
40 seconds. A longer `Retry-After` value from the API takes precedence. Each retry
also uses the shared request pacing. Other HTTP errors fail immediately. If all
five attempts return 429, check that the secret contains only the key value (no
quotes or email label), check for other applications using the same key, and
retry later. A masked secret in an Actions log confirms it was supplied, but does
not prove Semantic Scholar accepted it.

The runner logs each successfully resolved seed (identifier, paper ID, and title),
then sends one combined recommendations request for the resolved seed set. The
response log records the seed IDs, requested limit, and returned count. Raw
response bodies and request headers are not dumped. A response missing the
`recommendedPapers` array is an error rather than an empty digest.

Empty digest pages distinguish no returned recommendations, candidates excluded
by the publication-year rule (including missing years), and eligible papers that
already appeared in previous digests. If both filtering and deduplication removed
papers, the page shows both counts. API failures stop the run before publishing a
new page.

For LLM summaries, the optional `llama-cpp` backend sends requests to an
OpenAI-compatible `/chat/completions` endpoint. A local server only needs to run
while a local digest command is executing. A GitHub-hosted runner cannot reach
your computer's `localhost`. A hosted compatible endpoint is another option;
it requires a provider URL, model, and API key. The current workflow only wires
`S2_API_KEY`, so using hosted LLM summaries in CI also requires explicitly passing
`PAPERFEED_SUMMARIZER_BACKEND`, `LLAMA_CPP_BASE_URL`, `LLAMA_CPP_MODEL`, and
`LLAMA_CPP_API_KEY` (the latter from a separate repository secret). Compatibility
and valid summary JSON should be tested with the chosen provider.

## Summary style contract

### Historical report archive

Twelve original ChatGPT briefings (60 ranked items) have been transcribed into the
archive using their stated coverage-window end dates. The October 11 report also
retains the five papers originally generated by PaperFeed that day, for ten items
in the combined report. The original briefing prose, headings, rankings, tables,
formulas, links, introductions, and conclusions are preserved rather than passed
through the current summarizer or rewritten into its section schema.

The canonical transcriptions and date audit are in `data/backfill/`. See
[`data/backfill/README.md`](data/backfill/README.md) for the mapping and fidelity
checks. The PDF remains outside the repository; only the report transcriptions
and small formula assets are versioned. Original item titles are added to
`data/seen.json` so future discovery can avoid repeating them.

Rebuild these checked transcriptions without the PDF or an LLM:

```bash
python -m paperfeed.backfill
```

Rebuilding is deterministic and preserves the existing October 11 repository
papers. Checksum mismatches abort before any report is written.

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
- one static digest page per week,
- GitHub Actions weekly automation.

Do not implement tags, filters, search, accounts, databases, dashboards, or analytics in version 1.

## Example user experience

A normal weekly workflow is:

1. open the GitHub Pages site on iPhone,
2. read the latest weekly digest,
3. open the external PDF links for the papers worth deeper reading,
4. come back the next week for a new small batch.

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
- static weekly page generation
- GitHub Actions weekly run

### Possible later additions

Only add these if a concrete need appears:

- lightweight recency filtering,
- negative seeds,
- better metadata normalization,
- local non-versioned PDF cache,
- email notification with the weekly digest link.

## License

Choose the license you want for the repository code.

Common choices:

- MIT
- Apache-2.0

Do not assume rights to redistribute third-party PDFs.

## Status

This project is intentionally small by design.

If a proposed feature makes the system behave like a feed platform, search engine, document archive, or research management suite, it is probably out of scope.
