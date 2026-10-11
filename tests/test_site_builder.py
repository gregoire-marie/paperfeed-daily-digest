from __future__ import annotations

import unittest
from datetime import date

from paperfeed.models import Digest
from paperfeed.site_builder import build_digest_page


class SiteBuilderTests(unittest.TestCase):
    def test_empty_reason_is_html_escaped(self) -> None:
        digest = Digest(date(2026, 10, 11), [], empty_reason='No recommendations for <seed> & "related" papers.')
        page = build_digest_page(digest)
        self.assertIn("&lt;seed&gt; &amp; &quot;related&quot;", page)
        self.assertNotIn("<seed>", page)

    def test_unknown_empty_reason_does_not_invent_a_cause(self) -> None:
        page = build_digest_page(Digest(date(2026, 10, 11), []))
        self.assertIn("Discovery details were not recorded", page)
        self.assertNotIn("already seen or filtered out", page)


if __name__ == "__main__":
    unittest.main()
