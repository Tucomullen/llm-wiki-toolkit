import json
import os
import time
import unittest
from unittest import mock

import helpers
from helpers import WikiCase, page

from wikikit import extract, search
from wikikit.config import load_config


class SearchTests(WikiCase):
    def setUp(self):
        super().setUp()
        self.write("wiki/Tomato Care.md", page("Tomato Care", "Tomatoes love sun and café compost."))
        self.write("wiki/Basil.md", page("Basil", "Basil grows near tomatoes. Water gently."))
        self.write("wiki/projects-a/Deep.md", page("Deep", "Unique zeppelin word."))
        self.write("raw/talk.vtt", "WEBVTT\n\n1\n00:00:01.000 --> 00:00:04.000\nHello about marigolds\n")
        self.write("wiki/node_modules/Ignored.md", page("Ignored", "hidden quokka"))

    def index(self, *extra):
        code, out = self.cli("search", "index", *extra)
        self.assertEqual(code, 0, out)
        return out

    def test_index_query_and_ranking(self):
        self.index()
        code, out = self.cli("search", "query", "tomatoes")
        self.assertEqual(code, 0)
        self.assertIn("wiki/Tomato Care.md", out)
        self.assertIn("«Tomatoes»", out)

    def test_diacritics_and_excluded_dirs(self):
        self.index()
        self.assertIn("Tomato Care", self.cli("search", "query", "cafe")[1])
        self.assertIn("No results", self.cli("search", "query", "quokka")[1])

    def test_and_or_and_fts(self):
        self.index()
        self.assertIn("No results", self.cli("search", "query", "marigolds zeppelin")[1])
        out = self.cli("search", "query", "marigolds zeppelin", "--any")[1]
        self.assertIn("raw/talk.vtt", out)
        self.assertIn("Deep.md", out)
        code, out = self.cli("search", "query", "tomat*", "--fts")
        self.assertEqual(code, 0)
        self.assertIn("Tomato Care", out)
        code, out = self.cli("search", "query", 'AND OR "', "--fts")
        self.assertEqual(code, 2)
        self.assertIn("invalid FTS5 query", out)

    def test_filters_json_and_vtt_timestamps(self):
        self.index()
        code, out = self.cli("search", "query", "marigolds", "--source", "raw", "--json")
        data = json.loads(out)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["source"], "raw")
        self.assertNotIn("-->", data[0]["snippet"])
        data = json.loads(self.cli("search", "query", "zeppelin", "--project", "projects-a", "--json")[1])
        self.assertEqual(data[0]["project"], "projects-a")
        self.assertEqual(json.loads(self.cli("search", "query", "zeppelin", "--project", "nope", "--json")[1]), [])

    def test_incremental_update_and_delete(self):
        self.index()
        out = self.index()
        self.assertIn("unchanged 4", out)
        p = self.write("wiki/Basil.md", page("Basil", "Now about parsnips only."))
        os.utime(p, (time.time() + 5, time.time() + 5))
        out = self.index()
        self.assertIn("updated 1", out)
        self.assertIn("No results", self.cli("search", "query", "gently")[1])
        self.assertIn("Basil", self.cli("search", "query", "parsnips")[1])
        (self.root / "wiki" / "Basil.md").unlink()
        self.assertIn("removed 1", self.index())
        self.assertIn("No results", self.cli("search", "query", "parsnips")[1])

    def test_per_file_limit(self):
        self.write("wiki/Long.md", "---\ntitle: Long\n---\n\n# Long\n\n" + "\n\n".join(
            f"## S{i}\n\n" + ("kumquat filler words here. " * 60) for i in range(6)))
        self.index()
        data = json.loads(self.cli("search", "query", "kumquat", "--per-file", "2", "--json")[1])
        self.assertEqual(len(data), 2)
        data = json.loads(self.cli("search", "query", "kumquat", "--per-file", "5", "--json")[1])
        self.assertEqual(len(data), 5)

    def test_stats_and_full(self):
        self.index()
        code, out = self.cli("search", "stats")
        self.assertEqual(code, 0)
        self.assertIn("Files: 4", out)
        self.assertIn("added 4", self.index("--full"))

    def test_query_without_index(self):
        code, out = self.cli("search", "query", "x")
        self.assertEqual(code, 2)
        self.assertIn("search index", out)

    def test_cloud_only_files_skipped(self):
        real_stat_attr = search.is_cloud_only
        with mock.patch.object(search, "is_cloud_only", lambda st: True):
            self.index()
        code, out = self.cli("search", "stats")
        self.assertIn("cloud-only", out)
        self.assertIn("Files: 0", out)

    def test_eml_html_extraction_and_missing_extra(self):
        self.write("raw/mail.eml", "From: a@example.org\nTo: b@example.org\nSubject: Seed order\n"
                   "Content-Type: text/plain; charset=utf-8\n\nPlease order dahlia tubers.\n")
        self.write("raw/page.html", "<html><head><title>Hive</title><script>var x='secretjs';</script></head>"
                   "<body><h1>Bees</h1><p>Hive inspection notes.</p></body></html>")
        self.write("raw/file.docx", binary=b"not a real docx")
        self.index()
        self.assertIn("dahlia", self.cli("search", "query", "dahlia")[1])
        self.assertIn("Hive", self.cli("search", "query", "inspection")[1])
        self.assertIn("No results", self.cli("search", "query", "secretjs")[1])
        stats = self.cli("search", "stats")[1]
        self.assertIn("raw/file.docx", stats)

    def test_chunking_sizes_and_locations(self):
        text = "\n\n".join(f"Paragraph {i}. " + "word " * 80 for i in range(12))
        chunks = extract.chunk_unit(extract.Unit(text, "line", 0), 1200, 1800)
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(len(c.body) <= 1800 for c in chunks))
        self.assertEqual(chunks[0].loc, "L1")
        page_chunks = extract.chunk_unit(extract.Unit("hello", "page", 3), 1200, 1800)
        self.assertEqual(page_chunks[0].loc, "p3")

    def test_default_db_location(self):
        from pathlib import Path
        from wikikit.config import Config
        p = Config(root=Path(self.root)).resolved_db_path()
        self.assertEqual(p.suffix, ".sqlite")
        self.assertIn("wikikit", str(p))
        self.assertFalse(str(p).startswith(str(self.root)))


if __name__ == "__main__":
    unittest.main()
