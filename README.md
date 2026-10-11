# PaperFeed

A weekly research digest built from seed papers and Semantic Scholar recommendations.
It publishes a mobile-friendly static site with structured summaries and links to
papers, and avoids repeating papers already included in a digest.

## Quick start

Requires Python 3.11+. From the repository directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

1. Edit [`seeds.yaml`](seeds.yaml): choose your seed papers and adjust `top_k` and
   `min_publication_year`.
2. Set your Semantic Scholar API key, then generate a digest:

   ```bash
   export S2_API_KEY="your-key"
   python -m paperfeed.run_weekly
   ```

3. Open `site/index.html` in your browser.

A run writes `site/digests/YYYY-MM-DD.html`, refreshes `site/index.html`, and
updates `data/seen.json`. The report date defaults to the most recent Sunday.
If that page already exists, the command exits successfully without fetching
papers or changing files.

The default summarizer uses abstracts and needs no LLM service or OpenAI key.

## Automate and publish

1. Add the repository secret `S2_API_KEY` under **Settings > Secrets and variables
   > Actions**. Paste only the key value.
2. Under **Settings > Pages**, select **GitHub Actions** as the source.
3. Run **Actions > Weekly Digest > Run workflow** to check the setup.

[The workflow](.github/workflows/weekly.yml) generates a digest every Sunday at
06:17 UTC, commits the output, and deploys `site/` to GitHub Pages. Your computer
can be turned off. Pushes to `main` that change `site/` publish existing content
without generating another digest.

## Useful commands

```bash
# Override the number of papers for one run
python -m paperfeed.run_weekly --top-k 5

# Inspect all CLI options, including paths and an explicit report date
python -m paperfeed.run_weekly --help

# Check API access, seed resolution, and recommendations without writing a digest
python -m paperfeed.check_s2 --config seeds.yaml

# Run the test suite
python -m unittest discover -s tests
```

The API check prompts for the key in an interactive terminal; it does not save
it or use the existing `S2_API_KEY` value.

For contribution rules and product boundaries, see [`AGENTS.md`](AGENTS.md).

## Future work

Add optional LLM enrichment for **Why it matters**, **Limitations**, and
**Relevance to my research** only, using a hosted API with a free tier where
available. Ground these assessments in the candidate abstract, seed-paper
abstracts, and a short description of the research goals. Distinguish stated
limitations from inferred concerns, and mark insufficient evidence explicitly.

Keep **Main idea**, **Method**, and **Key results** on the existing deterministic
extraction path using abstracts supplied by Semantic Scholar. Keep **Basis** tied
to the source material actually used. Paper discovery and selection remain based
on Semantic Scholar recommendations.

This selective enrichment is planned, not implemented; the existing optional
LLM backend generates all six summary sections.

## Appendix

### Seed configuration

Each seed uses either a `paper_id` or a `doi`. Prefer the ID from the last segment
of the paper's Semantic Scholar URL if its DOI lookup fails. At least one
positive seed must resolve. Optional negative seeds steer recommendations away
from unwanted papers.

```yaml
positive_seeds:
  - paper_id: "a961442d9f0549d44b4de9dc2fc5161f0b150936"
negative_seeds: []
preferences:
  top_k: 5
  max_candidates_per_seed: 20
  min_publication_year: 2023
```

### Pipeline and summaries

The runner resolves seeds, makes one combined recommendations request, filters
by publication year, removes duplicates, and takes the first `top_k` papers in
API order. The candidate limit is `max_candidates_per_seed` times the number of
resolved positive seeds, capped at 500. With a minimum year configured, papers
with missing years are excluded.

[`data/seen.json`](data/seen.json) tracks DOI, Semantic Scholar ID, and normalized
title hash; a match on any of these prevents a repeat. Keep this file between runs.
The site links to source pages and PDFs rather than storing PDFs.

Generated summaries contain: **Why it matters**, **Main idea**, **Method**,
**Key results**, **Limitations**, and **Relevance to my research**. Both current
backends use abstracts and metadata only and label summaries `basis: abstract-only`.
The default backend selects abstract sentences and adds fixed context and
limitations text.

If no papers qualify, the page explains whether recommendations were empty,
publication-year filtering excluded candidates, or papers were already seen.
Retrieval failures stop generation instead of publishing an empty report.

`paperfeed-run-weekly` is also available after installation. The older
`paperfeed.run_daily` and `paperfeed-run-daily` commands are compatibility aliases
with the same weekly behavior.

### Optional LLM summaries

Start a `llama.cpp` server, then run:

```bash
python -m paperfeed.run_weekly \
  --summary-backend llama-cpp \
  --llama-base-url http://127.0.0.1:8080/v1 \
  --llama-model local-model
```

Equivalent environment variables are `PAPERFEED_SUMMARIZER_BACKEND`,
`LLAMA_CPP_BASE_URL`, and `LLAMA_CPP_MODEL`. Set `LLAMA_CPP_API_KEY` if the server
requires authentication. The backend uses an OpenAI-compatible
`/chat/completions` endpoint.

GitHub-hosted runners cannot reach your local server. To use a hosted compatible
endpoint in CI, pass these variables in the workflow and store its API key as a
separate secret. Test provider compatibility and summary JSON before enabling it.

### API troubleshooting

- **401/403:** check the key and API access permissions.
- **404 on a seed:** try its Semantic Scholar `paper_id`; a working DOI link does
  not guarantee Semantic Scholar can resolve the DOI.
- **429:** requests are paced at least 1.1 seconds apart and retried four times
  after 5, 10, 20, and 40 seconds, or longer if `Retry-After` requires it. Check
  whether other applications share the key, then retry later.
- **Local check succeeds but CI fails:** compare the repository secret with the
  entered key and start a fresh workflow run on the latest `main` commit.

The check uses public endpoints: success confirms API access from your computer,
but does not prove the key was accepted.

### Historical archive

Twelve imported ChatGPT briefings retain their original prose and formatting;
they do not follow the generated-summary schema. Their titles are included in
`seen.json`. Sources, date mapping, and fidelity checks are documented in
[`data/backfill/README.md`](data/backfill/README.md).

```bash
python -m paperfeed.backfill
```

This rebuilds the archive from versioned transcriptions without a PDF or LLM,
preserves the five original repository papers in the October 11 report, and
aborts on checksum mismatches before writing reports.
