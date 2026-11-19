"""Regression tests for the independently pinned safety policy."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

POLICY = Path(__file__).resolve().parents[1] / 'scripts' / 'trusted_safety_policy.py'
spec = importlib.util.spec_from_file_location('trusted_safety_policy', POLICY)
assert spec and spec.loader
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class TrustedSafetyPolicyTests(unittest.TestCase):
    def test_no_changes_allowed(self):
        self.assertEqual([], policy.evaluate_z(b''))

    def test_additions_allowed(self):
        self.assertEqual([], policy.evaluate_z(b'A\0README.md\0A\0raw/new.txt\0'))

    def test_normal_source_edit_allowed(self):
        self.assertEqual([], policy.evaluate_z(b'M\0src/wikikit/cli.py\0'))

    def test_deletion_denied(self):
        self.assertTrue(policy.evaluate_z(b'D\0README.md\0'))

    def test_existing_raw_edit_denied(self):
        self.assertTrue(policy.evaluate_z(b'M\0example/raw/evidence.txt\0'))

    def test_existing_log_edit_denied(self):
        self.assertTrue(policy.evaluate_z(b'M\0example/_meta/LOG.md\0'))

    def test_type_change_denied(self):
        self.assertTrue(policy.evaluate_z(b'T\0README.md\0'))

    def test_rename_denied(self):
        self.assertTrue(policy.evaluate_z(b'R100\0old\0new\0'))

    def test_copy_denied(self):
        self.assertTrue(policy.evaluate_z(b'C100\0old\0new\0'))

    def test_missing_terminator_fails_closed(self):
        with self.assertRaises(ValueError):
            policy.evaluate_z(b'M\0README.md')

    def test_missing_path_fails_closed(self):
        with self.assertRaises(ValueError):
            policy.evaluate_z(b'M\0')

    def test_unknown_status_fails_closed(self):
        with self.assertRaises(ValueError):
            policy.evaluate_z(b'X\0README.md\0')


if __name__ == '__main__':
    unittest.main()
