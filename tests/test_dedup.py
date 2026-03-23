from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paperfeed.dedup import SeenStore, filter_unseen_papers
from paperfeed.models import Paper


class DedupTests(unittest.TestCase):
    def test_seen_store_filters_by_doi_paper_id_and_title_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "seen.json"
            store = SeenStore(store_path)

            known_paper = Paper(
                paper_id="paper-1",
                doi="10.1000/known",
                title="Known Paper",
            )
            new_paper = Paper(
                paper_id="paper-2",
                doi="10.1000/new",
                title="Fresh Paper",
            )

            store.mark_summarized([known_paper], "2026-03-23")
            store.save()

            reloaded = SeenStore.load(store_path)
            unseen = filter_unseen_papers([known_paper, new_paper], reloaded)

            self.assertEqual([paper.paper_id for paper in unseen], ["paper-2"])


if __name__ == "__main__":
    unittest.main()
