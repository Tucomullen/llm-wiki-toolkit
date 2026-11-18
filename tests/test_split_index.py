import unittest
from unittest import mock

import helpers
from helpers import DEMO, DEMO_AFTER, WikiCase

from wikikit import splitindex


class SplitIndexTests(WikiCase):
    def test_dry_run_writes_nothing(self):
        self.copy_demo()
        before = (self.root / "_meta" / "INDEX.md").read_text(encoding="utf-8")
        code, out = self.cli("split-index", "_meta/INDEX.md", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)
        self.assertEqual((self.root / "_meta" / "INDEX.md").read_text(encoding="utf-8"), before)
        self.assertFalse((self.root / "_meta" / "index").exists())
        self.assertFalse((self.root / "_meta" / "_archive").exists())

    def test_split_demo_and_verify_clean(self):
        self.copy_demo()
        code, out = self.cli("split-index", "_meta/INDEX.md")
        self.assertEqual(code, 0, out)
        master = (self.root / "_meta" / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("<!-- KB-COUNT: 12 -->", master)
        self.assertIn("| Path | Entries in index | Files on disk | Sub-index |", master)
        idx = self.root / "_meta" / "index"
        self.assertTrue((idx / "_HISTORY.md").is_file())
        self.assertIn("first version of the index", (idx / "_HISTORY.md").read_text(encoding="utf-8"))
        self.assertNotIn("Change history", master)
        self.assertEqual(len(list((self.root / "_meta" / "_archive" / "index_backups").glob("INDEX-*.md"))), 1)
        code, out = self.cli("verify", "--fail-on-broken")
        self.assertEqual(code, 0, out)

    def test_matches_committed_after_example(self):
        self.copy_demo()
        self.cli("split-index", "_meta/INDEX.md")
        for f in (DEMO_AFTER / "_meta" / "index").glob("*.md"):
            self.assertEqual(f.read_text(encoding="utf-8"),
                             (self.root / "_meta" / "index" / f.name).read_text(encoding="utf-8"), f.name)
        self.assertEqual((DEMO_AFTER / "_meta" / "INDEX.md").read_text(encoding="utf-8"),
                         (self.root / "_meta" / "INDEX.md").read_text(encoding="utf-8"))

    def test_lost_link_aborts_without_writing(self):
        self.copy_demo()
        before = (self.root / "_meta" / "INDEX.md").read_text(encoding="utf-8")
        real = splitindex.render_subindex

        def lossy(piece):
            text = real(piece)
            return "\n".join(l for l in text.splitlines() if "Tomato Care" not in l) + "\n"

        with mock.patch.object(splitindex, "render_subindex", lossy):
            code, out = self.cli("split-index", "_meta/INDEX.md")
        self.assertEqual(code, 2)
        self.assertIn("aborting without writing", out)
        self.assertEqual((self.root / "_meta" / "INDEX.md").read_text(encoding="utf-8"), before)
        self.assertFalse((self.root / "_meta" / "index").exists())

    def test_check_links_preserved_unit(self):
        splitindex.check_links_preserved("- [[A]] — x\n- [[B]] — y\n", ["- [[A]] — x\n", "- [[B]] — y\n"])
        with self.assertRaises(splitindex.LinkLost):
            splitindex.check_links_preserved("- [[A]] — x\n- [[B]] — y\n", ["- [[A]] — x\n"])

    def test_existing_subindex_requires_force(self):
        self.copy_demo()
        self.assertEqual(self.cli("split-index", "_meta/INDEX.md")[0], 0)
        shutil_src = (helpers.REPO / "examples" / "demo-index-before" / "INDEX.md").read_text(encoding="utf-8")
        (self.root / "_meta" / "INDEX.md").write_text(shutil_src, encoding="utf-8")
        code, out = self.cli("split-index", "_meta/INDEX.md")
        self.assertEqual(code, 2)
        self.assertIn("--force", out)
        self.assertEqual(self.cli("split-index", "_meta/INDEX.md", "--force")[0], 0)

    def test_large_section_split_by_h3_and_threshold(self):
        entries = "\n".join(f"- [[P{i}]] — d" for i in range(4))
        text = f"# Idx\n\n## Big\n\n### One\n\n{entries}\n\n### Two\n\n- [[Q]] — d\n"
        self.write("_meta/INDEX.md", text)
        self.assertEqual(self.cli("split-index", "_meta/INDEX.md")[0], 0)
        names = sorted(p.name for p in (self.root / "_meta" / "index").glob("*.md"))
        self.assertEqual(names, ["big-one.md", "big-two.md"])

    def test_missing_file(self):
        self.assertEqual(self.cli("split-index", "nope.md")[0], 2)


if __name__ == "__main__":
    unittest.main()
