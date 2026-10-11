# Historical briefing transcription audit

Source: the owner's PDF export titled **SSA ML Paper Brief**, created on
October 11, 2026. Its SHA-256 checksum is recorded in `manifest.json`. The PDF is
one tall, tagged page; `source_pdf_top` and `source_pdf_bottom` locate each report
in PDF points from the top of that page.

All 12 full briefings are preserved, including all 60 ranked items, their tables,
citations, introductions, reading priorities, recommended experiments and
conclusions. No scientific content was added, corrected, summarized or omitted.
The original English/French language and literal TeX strings remain unchanged.
Formula glyphs and drawn mathematical symbols are rendered from the source into
small transparent image assets for faithful mobile reading.

Only conversation material that is not a report was excluded: the user's prompts,
scheduling acknowledgments, follow-up discussion between July 26 and August 9,
and ChatGPT application controls. Instructions within the conversation were
treated as source material, not executed as instructions for this import.

## Date mapping

The page date follows each report's stated coverage end. Full reports were kept
together rather than split, repeated or fabricated to fill every daily gap.

| Archive date | Evidence in the PDF |
| --- | --- |
| 2026-07-12 | Baseline window: 27 April–12 July. Message timestamp is July 11 at 19:55; the coverage end determines the Sunday archive date. |
| 2026-07-26 | Coverage window: 13–26 July; message timestamp July 26. |
| 2026-08-09 | Heading: “3 au 9 août 2026”; no separate dated message marker is visible. |
| 2026-08-16 | Heading: “10 au 16 août 2026”; message timestamp August 16. |
| 2026-08-23 | Heading says “nouveautés depuis le précédent briefing”; message timestamp August 23 at 12:35 supplies the date. |
| 2026-08-30 | Heading: 24–30 August; message timestamp August 30. Replaces a previously empty repository page. |
| 2026-09-06 | Heading: 31 August to 6 September; message timestamp September 6. |
| 2026-09-13 | Heading: 7–13 September; message timestamp September 13. |
| 2026-09-20 | Heading: 14–20 September; message timestamp September 20. |
| 2026-09-27 | Heading: 21–27 September; message timestamp September 27. |
| 2026-10-04 | Heading: 28 September to 4 October; message marker says “dimanche”. |
| 2026-10-11 | Heading: 5–11 October; message marker says “aujourd’hui”, matching PDF creation date October 11. Blended with the five existing repository papers. |

There are no separate July 19 or August 2 reports in the supplied PDF. The July 26
briefing covers two weeks. Nothing was invented for the absent slots. Earlier
repository pages remain available and unchanged.

## Preserved sources and checks

- `reports/YYYY-MM-DD.html` is the canonical formatted transcription.
- `reports/YYYY-MM-DD.txt` is the spatial text extraction from the corresponding
  PDF region, including mathematical glyphs missed by simpler extraction tools.
- `reports/2026-10-11-repo.html` retains the five original repository papers and
  their summaries. On October 11, 2026, their visible Basis fields were replaced
  with collapsed Abstract sections containing the complete abstracts retrieved
  from the Semantic Scholar Graph API. The manifest records the updated checksum.
- `manifest.json` records dates, source regions, text/HTML checksums, ranked
  titles, source URLs, and exact source-character accounting.
- `site/assets/backfill/` contains only mathematical formula images, not PDFs or
  page screenshots.

Every visible non-whitespace text character in each source report was accounted
for exactly once during transcription. Tests compare the source/rendered
character inventories, require all source URLs and formulas, verify all 12
reports and 60 items, preserve the five existing repository cards, and verify
that rebuilding is idempotent. HTML escaping and line wrapping are presentation
changes; the report content is not rewritten.

Source limitation: the September 13 briefing contains a displayed question whose
PDF text ends at “how qu”. There are no remaining glyphs beyond the content
column in the PDF. This fragment is retained exactly as provided; no missing
words were guessed. A future Markdown source can supply the original ending.

Rebuild with `PYTHONPATH=src python3 -m paperfeed.backfill`. This needs only the
standard library and the versioned source transcriptions. Modifying an archived
transcription without updating its audit checksum is rejected explicitly.
