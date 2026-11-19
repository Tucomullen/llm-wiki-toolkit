"""Regression tests for the Git change safety checks (no working repo needed)."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "safety_guard.py"
spec = importlib.util.spec_from_file_location("safety_guard", GUARD)
assert spec and spec.loader
safety_guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety_guard)


class SafetyGuardTests(unittest.TestCase):
    def test_additions_allowed_including_new_raw(self):
        self.assertEqual([], safety_guard.evaluate("A\tREADME.md\nA\traw/new.txt"))

    def test_normal_source_edits_allowed(self):
        self.assertEqual([], safety_guard.evaluate("M\tsrc/wikikit/cli.py"))

    def test_deletions_rejected(self):
        self.assertTrue(safety_guard.evaluate("D\tREADME.md"))

    def test_existing_raw_edits_rejected(self):
        self.assertTrue(safety_guard.evaluate("M\texamples/demo-wiki/raw/note.txt"))

    def test_existing_logs_edits_rejected(self):
        self.assertTrue(safety_guard.evaluate("M\texamples/demo-wiki/_meta/LOG.md"))

    def test_renames_rejected(self):
        self.assertTrue(safety_guard.evaluate("R100\told.md\tnew.md"))

    def test_copies_require_review(self):
        self.assertTrue(safety_guard.evaluate("C100\told.md\tnew.md"))


if __name__ == "__main__":
    unittest.main()
