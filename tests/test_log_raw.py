import unittest

from helpers import WikiCase

ENTRY = "## [2026-05-01] NOTE | First thing\nBody line.\n"


class LogAppendTests(WikiCase):
    def setUp(self):
        super().setUp()
        self.write("_meta/LOG.md", "# Log\n\n## [2026-04-01] INIT | Start\nHello.\n")
        self.logp = self.root / "_meta" / "LOG.md"

    def test_append_ok_and_archive(self):
        e = self.write("_meta/_log_pending_a.md", ENTRY)
        old = self.logp.read_bytes()
        code, out = self.cli("log", "append", str(e))
        self.assertEqual(code, 0, out)
        new = self.logp.read_bytes()
        self.assertTrue(new.startswith(old))
        self.assertIn(b"## [2026-05-01] NOTE | First thing", new)
        self.assertFalse(e.exists())
        self.assertTrue((self.root / "_meta" / "_archive" / "log_applied" / "_log_pending_a.md").is_file())

    def test_duplicate_header_rejected(self):
        e = self.write("_meta/e.md", "## [2026-04-01] INIT | Start\nAgain.\n")
        before = self.logp.read_bytes()
        code, out = self.cli("log", "append", str(e))
        self.assertEqual(code, 2)
        self.assertIn("already exists", out)
        self.assertEqual(self.logp.read_bytes(), before)
        self.assertTrue(e.exists())

    def test_bad_header_rejected(self):
        for bad in ("No header here\n", "## 2026-05-01 NOTE | x\n", "## [2026-05-01] note | x\n", ""):
            e = self.write("_meta/e.md", bad)
            self.assertEqual(self.cli("log", "append", str(e))[0], 2, bad)

    def test_second_append_and_missing_trailing_newline(self):
        self.logp.write_bytes(self.logp.read_bytes().rstrip(b"\n"))
        e1 = self.write("_meta/e1.md", ENTRY)
        self.assertEqual(self.cli("log", "append", str(e1))[0], 0)
        e2 = self.write("_meta/e2.md", "## [2026-05-02] NOTE | Second\nMore.\n")
        self.assertEqual(self.cli("log", "append", str(e2))[0], 0)
        text = self.logp.read_text(encoding="utf-8")
        self.assertLess(text.index("First thing"), text.index("Second"))
        self.assertEqual(self.cli("log", "append", str(self.write("_meta/e3.md", ENTRY)))[0], 2)

    def test_missing_log(self):
        self.logp.unlink()
        e = self.write("_meta/e.md", ENTRY)
        self.assertEqual(self.cli("log", "append", str(e))[0], 2)


class RawSaveTests(WikiCase):
    def pending(self, name, text="data"):
        return self.write(f"_meta/_raw_pending/{name}", text)

    def test_save_ok(self):
        f = self.pending("notes.txt", "hello")
        code, out = self.cli("raw", "save", str(f))
        self.assertEqual(code, 0, out)
        self.assertEqual((self.root / "raw" / "notes.txt").read_text(encoding="utf-8"), "hello")
        self.assertFalse(f.exists())

    def test_rename(self):
        f = self.pending("tmp.txt")
        self.assertEqual(self.cli("raw", "save", str(f), "--name", "2026-05-01_final.txt")[0], 0)
        self.assertTrue((self.root / "raw" / "2026-05-01_final.txt").is_file())

    def test_never_overwrites(self):
        self.write("raw/notes.txt", "original")
        f = self.pending("notes.txt", "new")
        code, out = self.cli("raw", "save", str(f))
        self.assertEqual(code, 2)
        self.assertIn("never overwritten", out)
        self.assertEqual((self.root / "raw" / "notes.txt").read_text(encoding="utf-8"), "original")
        self.assertTrue(f.exists())

    def test_bad_names_rejected(self):
        f = self.pending("a.txt")
        for bad in ("../evil.txt", "..", "sub/dir.txt", "sub\\dir.txt", "a..b.txt", ".hidden", "", "x:y.txt"):
            code, out = self.cli("raw", "save", str(f), "--name", bad)
            self.assertEqual(code, 2, bad)
        self.assertTrue(f.exists())
        self.assertFalse((self.root / "evil.txt").exists())
        self.assertFalse((self.tmp / "evil.txt").exists())

    def test_only_from_pending_folder(self):
        f = self.write("elsewhere/a.txt", "x")
        code, out = self.cli("raw", "save", str(f))
        self.assertEqual(code, 2)
        self.assertIn("_raw_pending", out)
        nested = self.write("_meta/_raw_pending/sub/b.txt", "x")
        self.assertEqual(self.cli("raw", "save", str(nested))[0], 2)


if __name__ == "__main__":
    unittest.main()
