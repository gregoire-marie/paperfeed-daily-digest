from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from paperfeed.models import Digest, DigestEntry, Paper


_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#315c72"/>
  <g fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round">
    <path d="M16 9c-3-2-6-2-10-1v16c4-1 7-1 10 1 3-2 6-2 10-1V8c-4-1-7-1-10 1Z"/>
    <path d="M16 9v16M9 12h4M9 16h4M19 12h4M19 16h4"/>
  </g>
</svg>
"""


# Palette and typography shared with gregoire-marie.github.io/src/styles/global.css.
_SITE_STYLE = """
    :root {
      color-scheme: light;
      --bg: #f7f7f4;
      --panel: #ffffff;
      --sunken: #efefea;
      --ink: #171b1f;
      --muted: #4d555c;
      --line: #d5d7d3;
      --line-strong: #aeb4b3;
      --accent: #315c72;
      --accent-soft: #e5ecef;
      --font-sans: "IBM Plex Sans", system-ui, sans-serif;
      --font-display: "Space Grotesk", system-ui, sans-serif;
      --font-mono: "IBM Plex Mono", ui-monospace, monospace;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        color-scheme: dark;
        --bg: #111416;
        --panel: #181c1e;
        --sunken: #0d1012;
        --ink: #e7e9e7;
        --muted: #abb2b5;
        --line: #2b3033;
        --line-strong: #495157;
        --accent: #8ab0c0;
        --accent-soft: #1e2b31;
      }
    }
    * { box-sizing: border-box; }
    html {
      background: var(--bg);
      color: var(--ink);
      font: 16px/1.65 var(--font-sans);
      -webkit-font-smoothing: antialiased;
    }
    body { margin: 0; min-height: 100vh; }
    ::selection { background: var(--accent-soft); color: var(--ink); }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; text-underline-offset: 4px; }
    a:focus-visible, summary:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 4px;
    }
    .hero, .stack {
      width: min(960px, calc(100% - 48px));
      margin-inline: auto;
    }
    .hero { padding: 80px 0 36px; }
    .eyebrow {
      color: var(--accent);
      font: 500 .78rem/1.4 var(--font-mono);
      letter-spacing: .13em;
      text-transform: uppercase;
      margin: 0 0 20px;
    }
    h1 {
      font: 700 clamp(2.2rem, 6vw, 4.2rem)/1.05 var(--font-display);
      letter-spacing: -.045em;
      margin: 0;
      max-width: 18ch;
    }
    .lede {
      max-width: 660px;
      color: var(--muted);
      font-size: 1.05rem;
      margin: 22px 0;
    }
    .stack { display: grid; gap: 28px; padding-bottom: 64px; }
    .panel {
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 32px;
    }
    h2 {
      font: 600 1.5rem/1.3 var(--font-display);
      letter-spacing: -.025em;
      margin: 0 0 16px;
      overflow-wrap: anywhere;
    }
    .digest-list {
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }
    .digest-card {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      padding: 20px;
      border: 1px solid var(--line);
      border-radius: 4px;
      color: var(--ink);
    }
    .digest-card:hover {
      background: var(--accent-soft);
      border-color: var(--accent);
      text-decoration: none;
    }
    .digest-card strong { font: 600 1rem/1.4 var(--font-display); }
    .digest-card span {
      color: var(--muted);
      font: 400 1rem/1.4 var(--font-mono);
      white-space: nowrap;
    }
    .meta { color: var(--muted); font-size: 1rem; margin: 10px 0; }
    .abstract {
      margin: 24px 0;
      padding-block: 16px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }
    .abstract summary { cursor: pointer; font-weight: 600; color: var(--accent); }
    .abstract p {
      color: var(--muted);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin-bottom: 0;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: minmax(0, 170px) minmax(0, 1fr);
      gap: 20px 28px;
      margin: 0;
    }
    .summary-grid dt {
      min-width: 0;
      color: var(--accent);
      font: 500 1rem/1.65 var(--font-mono);
      letter-spacing: .04em;
      text-transform: uppercase;
      padding-top: 3px;
    }
    .summary-grid dd { min-width: 0; margin: 0; color: var(--muted); }
    .summary-grid dd, .meta, .empty-state p { overflow-wrap: anywhere; }
    .link-row { display: flex; flex-wrap: wrap; gap: 10px; margin: 22px 0; }
    .link-row a {
      display: inline-flex;
      align-items: center;
      min-height: 44px;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      padding: 8px 16px;
      font-size: 1rem;
    }
    .link-row a:hover { background: var(--accent-soft); border-color: var(--accent); }
    .back-link { display: inline-flex; align-items: center; min-height: 44px; font-weight: 500; }
    .empty-state { padding: 32px; }
    .empty-state p { color: var(--muted); }
    code { font: 1em var(--font-mono); background: var(--sunken); padding: .1rem .35rem; }
    @media (max-width: 640px) {
      .hero, .stack { width: calc(100% - 32px); }
      .hero { padding: 48px 0 24px; }
      .stack { gap: 20px; padding-bottom: 40px; }
      .panel { padding: 22px 18px; }
      .summary-grid { grid-template-columns: 1fr; gap: 8px; }
      .summary-grid dd { margin-bottom: 16px; }
      .summary-grid dd:last-child { margin-bottom: 0; }
      .digest-list { grid-template-columns: 1fr; }
      .digest-card { padding: 18px 14px; }
    }
"""


def write_digest_site(digest: Digest, site_dir: str | Path) -> Path:
    """Write a digest, the refreshed homepage, and the shared favicon."""
    site_path = Path(site_dir)
    digest_dir = site_path / "digests"
    digest_dir.mkdir(parents=True, exist_ok=True)
    (site_path / "favicon.svg").write_text(_FAVICON_SVG, encoding="utf-8")

    digest_path = digest_dir / f"{digest.digest_date.isoformat()}.html"
    digest_path.write_text(build_digest_page(digest), encoding="utf-8")

    index_path = site_path / "index.html"
    index_path.write_text(build_index_page(site_path, latest_digest=digest), encoding="utf-8")
    return digest_path


def build_index_page(site_dir: Path, latest_digest: Digest | None = None) -> str:
    digest_dir = site_dir / "digests"
    digest_paths = sorted(digest_dir.glob("*.html"), reverse=True)
    cards = []
    for path in digest_paths:
        digest_date = date.fromisoformat(path.stem)
        count_label = f"{path.read_text(encoding='utf-8').count('<article class=\"panel paper-card')} items"
        if latest_digest and latest_digest.digest_date == digest_date:
            count_label = f"{len(latest_digest.entries)} items"
        cards.append(
            f"""
            <a class="digest-card" href="digests/{escape(path.name)}">
              <strong>{escape(digest_date.strftime('%B %d, %Y'))}</strong>
              <span>{count_label}</span>
            </a>
            """.strip()
        )

    if not cards:
        cards.append(
            """
            <section class="empty-state">
              <h2>No digests yet</h2>
              <p>Run <code>python -m paperfeed.run_weekly</code> to generate the first weekly page.</p>
            </section>
            """
        )

    return _page_shell(
        title="PaperFeed",
        description="A weekly selection of papers connected to my research, with concise summaries.",
        body=f"""
        <header class="hero">
          <p class="eyebrow">PaperFeed</p>
          <h1>Weekly paper digest</h1>
          <p class="lede">
            A weekly selection of papers connected to my research, with concise summaries.
          </p>
          <p><a class="back-link" href="https://github.com/gregoire-marie/paperfeed-daily-digest">View source on GitHub</a></p>
        </header>
        <main class="stack">
          <section class="panel">
            <h2>Digests</h2>
            <div class="digest-list">
              {''.join(cards)}
            </div>
          </section>
        </main>
        """,
    )


def build_digest_page(digest: Digest) -> str:
    """Render a weekly page using its recorded explanation for an empty result."""
    if digest.entries:
        content = "".join(build_entry_card(entry) for entry in digest.entries)
    else:
        reason = digest.empty_reason or "No papers were selected. Discovery details were not recorded for this digest."
        content = f"""
        <section class="panel empty-state">
          <h2>No new papers this week</h2>
          <p>{escape(reason)}</p>
        </section>
        """

    return _page_shell(
        title=f"PaperFeed digest for {digest.digest_date.isoformat()}",
        description=f"Weekly digest for {digest.digest_date.isoformat()}",
        favicon_href="../favicon.svg",
        body=f"""
        <header class="hero">
          <p class="eyebrow">PaperFeed digest</p>
          <h1>{escape(digest.digest_date.strftime('%B %d, %Y'))}</h1>
          <p class="lede">{len(digest.entries)} papers selected for the week.</p>
          <p><a class="back-link" href="../index.html">Back to index</a></p>
        </header>
        <main class="stack">
          {content}
        </main>
        """,
    )


def build_entry_card(entry: DigestEntry) -> str:
    """Render a paper with the shared summary fields and its available abstract."""
    paper = entry.paper
    authors = format_authors(paper.authors)
    meta = " · ".join(part for part in [authors, paper.venue, _format_year(paper), _format_citations(paper)] if part)
    matched_seed_line = ""
    if entry.matched_seed_titles:
        matched_seed_line = (
            f"<p class=\"meta\">Matched seeds: {escape(', '.join(entry.matched_seed_titles))}</p>"
        )

    links = []
    links.append(
        f"<a href=\"{escape(source_url_for_paper(paper))}\" target=\"_blank\" rel=\"noreferrer\">Source</a>"
    )
    if paper.pdf_url:
        links.append(
            f"<a href=\"{escape(paper.pdf_url)}\" target=\"_blank\" rel=\"noreferrer\">PDF</a>"
        )

    summary = entry.summary
    sections = [
        ("Why it matters", summary.why_it_matters),
        ("Main idea", summary.main_idea),
        ("Method", summary.method),
        ("Key results", summary.key_results),
        ("Limitations", summary.limitations),
        ("Relevance to my research", summary.relevance_to_my_research),
    ]
    summary_html = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in sections
    )

    card_html = f"""
    <article class="panel paper-card">
      <h2>{escape(paper.title)}</h2>
      <p class="meta">{escape(meta)}</p>
      {matched_seed_line}
      <p class="link-row">{' '.join(links)}</p>
      <details class="abstract">
        <summary>Abstract</summary>
        <p>{escape(paper.abstract or 'No abstract available.')}</p>
      </details>
      <dl class="summary-grid">
        {summary_html}
      </dl>
    </article>
    """
    return "\n".join(line.rstrip() for line in card_html.splitlines()) + "\n"


def source_url_for_paper(paper: Paper) -> str:
    base_url = paper.url or f"https://www.semanticscholar.org/paper/{paper.paper_id}"
    parsed = urlparse(base_url)
    if "semanticscholar.org" not in parsed.netloc:
        return base_url

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("utm_source", "api")
    return urlunparse(parsed._replace(query=urlencode(query)))


def format_authors(authors: list[object]) -> str:
    author_names = [getattr(author, "name", "Unknown author") for author in authors]
    if not author_names:
        return "Unknown authors"
    if len(author_names) <= 4:
        return ", ".join(author_names)
    return ", ".join(author_names[:4]) + f" +{len(author_names) - 4} more"


def _format_year(paper: Paper) -> str | None:
    if paper.publication_date:
        return paper.publication_date
    if paper.year:
        return str(paper.year)
    return None


def _format_citations(paper: Paper) -> str | None:
    if paper.citation_count is None:
        return None
    label = "citation" if paper.citation_count == 1 else "citations"
    return f"{paper.citation_count} {label}"


def _page_shell(*, title: str, description: str, body: str, favicon_href: str = "favicon.svg") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#315c72">
  <link rel="icon" type="image/svg+xml" href="{escape(favicon_href)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&amp;family=IBM+Plex+Sans:wght@400;500;600&amp;family=Space+Grotesk:wght@500;600;700&amp;display=swap" rel="stylesheet">
  <style>{_SITE_STYLE}  </style>
</head>
<body>
  {body}
</body>
</html>
"""
