"""Positive, negative and fail-closed regression tests for trusted PR safety."""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "trusted_pr_policy.py"
spec = importlib.util.spec_from_file_location("trusted_pr_policy", SCRIPT)
assert spec and spec.loader
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def changed(name, status, **kwargs):
    return dict(filename=name, status=status, **kwargs)


class TrustedPrPolicyTests(unittest.TestCase):
    def test_new_files_allowed(self):
        self.assertEqual([], policy.evaluate_files([changed("raw/new.txt", "added"), changed("README.md", "added")]))

    def test_normal_source_edits_allowed(self):
        self.assertEqual([], policy.evaluate_files([changed("src/code.py", "modified")]))

    def test_deletion_denied(self):
        self.assertTrue(policy.evaluate_files([changed("README.md", "removed")]))

    def test_raw_edit_denied(self):
        self.assertTrue(policy.evaluate_files([changed("examples/raw/f.txt", "modified")]))

    def test_log_edit_denied(self):
        self.assertTrue(policy.evaluate_files([changed("wiki/_meta/LOG.md", "modified")]))

    def test_rename_denied(self):
        self.assertTrue(policy.evaluate_files([changed("new.md", "renamed", previous_filename="old.md")]))

    def test_locked_workflow_edit_denied(self):
        self.assertTrue(policy.evaluate_files([changed(".github/workflows/trusted-safety.yml", "modified")]))

    def test_locked_script_edit_denied(self):
        self.assertTrue(policy.evaluate_files([changed("scripts/trusted_pr_policy.py", "modified")]))

    def test_type_change_denied(self):
        self.assertTrue(policy.evaluate_files([changed("file.md", "changed")]))

    def test_unknown_status_fails_closed(self):
        with self.assertRaises(ValueError):
            policy.evaluate_files([changed("file.md", "unknown")])

    def test_malformed_entry_fails_closed(self):
        with self.assertRaises(ValueError):
            policy.evaluate_files([{"status": "added"}])

    def test_pr_head_race_fails_closed(self):
        with patch.object(policy, "get_json", return_value={"base": {"sha": "old"}, "head": {"sha": "new"}}):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "old", "expected", "token")

    def test_pagination_and_normal_changes(self):
        first = [changed(f"file{i}.txt", "added") for i in range(100)]
        second = [changed("src/program.py", "modified")]
        with patch.object(policy, "get_json", side_effect=[
            {"base": {"sha": "base"}, "head": {"sha": "head"}, "changed_files": 101}, first, second
        ]):
            self.assertEqual([], policy.verify_pr("owner/repo", 1, "base", "head", "token"))

    def test_mismatched_count_fails_closed(self):
        with patch.object(policy, "get_json", side_effect=[
            {"base": {"sha": "base"}, "head": {"sha": "head"}, "changed_files": 2},
            [changed("README.md", "added")]
        ]):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "base", "head", "token")

    def test_no_files_fails_closed(self):
        with patch.object(policy, "get_json", side_effect=[
            {"base": {"sha": "base"}, "head": {"sha": "head"}, "changed_files": 0}, []
        ]):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "base", "head", "token")


if __name__ == "__main__":
    unittest.main()
