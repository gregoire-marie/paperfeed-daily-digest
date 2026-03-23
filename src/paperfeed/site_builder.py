from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from paperfeed.models import Digest, DigestEntry, Paper


def write_digest_site(digest: Digest, site_dir: str | Path) -> Path:
    site_path = Path(site_dir)
    digest_dir = site_path / "digests"
    digest_dir.mkdir(parents=True, exist_ok=True)

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
        count_label = ""
        if latest_digest and latest_digest.digest_date == digest_date:
            count_label = f"{len(latest_digest.entries)} papers"
        cards.append(
            f"""
            <a class="digest-card" href="digests/{escape(path.name)}">
              <strong>{escape(digest_date.strftime('%B %d, %Y'))}</strong>
              <span>{count_label or 'Open digest'}</span>
            </a>
            """
        )

    if not cards:
        cards.append(
            """
            <section class="empty-state">
              <h2>No digests yet</h2>
              <p>Run <code>python -m paperfeed.run_daily</code> to generate the first daily page.</p>
            </section>
            """
        )

    return _page_shell(
        title="PaperFeed",
        description="A minimal daily research digest built from your seed papers.",
        body=f"""
        <header class="hero">
          <p class="eyebrow">PaperFeed</p>
          <h1>Daily paper digest</h1>
          <p class="lede">
            A small, static reading surface for high-signal papers related to your research.
          </p>
        </header>
        <main class="stack">
          <section class="panel">
            <h2>Digests</h2>
            <div class="digest-list">
              {''.join(cards)}
            </div>
          </section>
          <section class="footnote">
            <p>Discovery metadata is sourced from Semantic Scholar.</p>
          </section>
        </main>
        """,
    )


def build_digest_page(digest: Digest) -> str:
    if digest.entries:
        content = "".join(build_entry_card(entry) for entry in digest.entries)
    else:
        content = """
        <section class="panel empty-state">
          <h2>No new papers today</h2>
          <p>All retrieved candidates were already seen or filtered out. The site will update again on the next run.</p>
        </section>
        """

    return _page_shell(
        title=f"PaperFeed digest for {digest.digest_date.isoformat()}",
        description=f"Daily digest for {digest.digest_date.isoformat()}",
        body=f"""
        <header class="hero">
          <p class="eyebrow">PaperFeed digest</p>
          <h1>{escape(digest.digest_date.strftime('%B %d, %Y'))}</h1>
          <p class="lede">{len(digest.entries)} papers selected for the day.</p>
          <p><a class="back-link" href="../index.html">Back to index</a></p>
        </header>
        <main class="stack">
          {content}
          <section class="footnote">
            <p>Metadata and recommendation discovery are powered by Semantic Scholar.</p>
          </section>
        </main>
        """,
    )


def build_entry_card(entry: DigestEntry) -> str:
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
        ("Basis", summary.basis),
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

    return f"""
    <article class="panel paper-card">
      <h2>{escape(paper.title)}</h2>
      <p class="meta">{escape(meta)}</p>
      {matched_seed_line}
      <p class="link-row">{' '.join(links)}</p>
      <dl class="summary-grid">
        {summary_html}
      </dl>
    </article>
    """


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


def _page_shell(*, title: str, description: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <style>
    :root {{
      --bg: #f4efe3;
      --panel: rgba(255, 251, 242, 0.9);
      --ink: #20261f;
      --muted: #5e655d;
      --line: rgba(32, 38, 31, 0.12);
      --accent: #1e6a4c;
      --accent-soft: #ddeee6;
      --shadow: 0 18px 40px rgba(32, 38, 31, 0.08);
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(30, 106, 76, 0.12), transparent 32%),
        radial-gradient(circle at top right, rgba(178, 111, 56, 0.12), transparent 28%),
        linear-gradient(180deg, #fbf7ee 0%, var(--bg) 100%);
      min-height: 100vh;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .hero, .stack {{
      width: min(860px, calc(100vw - 32px));
      margin: 0 auto;
    }}
    .hero {{
      padding: 48px 0 24px;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 0.78rem;
      color: var(--muted);
      margin: 0 0 10px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2.2rem, 6vw, 4.2rem);
      line-height: 0.95;
      max-width: 12ch;
    }}
    .lede {{
      max-width: 42rem;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.6;
    }}
    .stack {{
      display: grid;
      gap: 18px;
      padding-bottom: 48px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 22px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .digest-list {{
      display: grid;
      gap: 12px;
    }}
    .digest-card {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 16px 18px;
      border-radius: 18px;
      background: white;
      border: 1px solid var(--line);
    }}
    .paper-card h2, .panel h2 {{
      margin-top: 0;
    }}
    .meta {{
      color: var(--muted);
      line-height: 1.5;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: minmax(0, 180px) minmax(0, 1fr);
      gap: 10px 16px;
      margin: 0;
    }}
    .summary-grid dt {{
      font-weight: 700;
      color: var(--ink);
    }}
    .summary-grid dd {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .link-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin: 16px 0 20px;
    }}
    .link-row a {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--accent-soft);
      padding: 8px 12px;
      border-radius: 999px;
    }}
    .back-link {{
      font-weight: 700;
    }}
    .empty-state {{
      text-align: center;
      padding: 28px;
    }}
    .footnote {{
      color: var(--muted);
      font-size: 0.94rem;
      padding-bottom: 6px;
    }}
    code {{
      font-family: "SFMono-Regular", "SF Mono", Menlo, Consolas, monospace;
      background: rgba(32, 38, 31, 0.06);
      padding: 0.1rem 0.35rem;
      border-radius: 6px;
    }}
    @media (max-width: 640px) {{
      .hero {{
        padding-top: 32px;
      }}
      .panel {{
        padding: 18px;
        border-radius: 20px;
      }}
      .summary-grid {{
        grid-template-columns: 1fr;
      }}
      .digest-card {{
        flex-direction: column;
        align-items: flex-start;
      }}
    }}
  </style>
</head>
<body>
  {body}
</body>
</html>
"""
