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

    def test_stale_added_locked_workflow_rejected(self):
        self.assertTrue(policy.evaluate_files(
            [changed(".github/workflows/trusted-safety.yml", "added")],
            frozenset({".github/workflows/trusted-safety.yml"}),
        ))

    def test_stale_added_locked_script_rejected(self):
        self.assertTrue(policy.evaluate_files(
            [changed("scripts/trusted_pr_policy.py", "added")],
            frozenset({"scripts/trusted_pr_policy.py"}),
        ))

    def test_stale_added_raw_rejected(self):
        self.assertTrue(policy.evaluate_files(
            [changed("examples/raw/existing.txt", "added")],
            frozenset({"examples/raw/existing.txt"}),
        ))

    def test_genuinely_new_raw_allowed(self):
        self.assertEqual([], policy.evaluate_files(
            [changed("examples/raw/new.txt", "added")],
            frozenset({"examples/raw/other.txt"}),
        ))

    def mock_api(self, files, *, changed_files=None, current_paths=(), final_sha="current"):
        """REST response sequence: PR, base ref, commit, tree, files, PR, base ref."""
        pr = {"base": {"sha": "old-base", "ref": "main"},
              "head": {"sha": "head"}, "changed_files": len(files) if changed_files is None else changed_files}
        return [pr,
                {"object": {"sha": "current"}},
                {"tree": {"sha": "tree"}},
                {"truncated": False, "tree": [
                    {"path": path, "type": "blob"} for path in current_paths
                ]},
                files, pr, {"object": {"sha": final_sha}}]

    def test_stale_pr_full_flow_rejects_existing_workflow(self):
        files = [changed(".github/workflows/trusted-safety.yml", "added")]
        with patch.object(policy, "get_json", side_effect=self.mock_api(
            files, current_paths=[".github/workflows/trusted-safety.yml"]
        )):
            problems = policy.verify_pr("owner/repo", 1, "old-base", "head", "token")
        self.assertTrue(problems)
        self.assertIn("current base", problems[0])

    def test_stale_pr_full_flow_allows_genuinely_new_file(self):
        files = [changed("wiki/raw/new.txt", "added")]
        with patch.object(policy, "get_json", side_effect=self.mock_api(
            files, current_paths=["wiki/raw/existing.txt"]
        )):
            self.assertEqual([], policy.verify_pr("owner/repo", 1, "old-base", "head", "token"))

    def test_pr_head_race_fails_closed(self):
        with patch.object(policy, "get_json", return_value={
            "base": {"sha": "old-base", "ref": "main"}, "head": {"sha": "different"}
        }):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "old-base", "expected", "token")

    def test_pagination_and_normal_changes(self):
        first = [changed(f"file{i}.txt", "added") for i in range(100)]
        second = [changed("src/program.py", "modified")]
        calls = self.mock_api(first + second)
        calls[4:5] = [first, second]
        with patch.object(policy, "get_json", side_effect=calls):
            self.assertEqual([], policy.verify_pr("owner/repo", 1, "old-base", "head", "token"))

    def test_mismatched_count_fails_closed(self):
        with patch.object(policy, "get_json", side_effect=self.mock_api(
            [changed("README.md", "added")], changed_files=2
        )):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "old-base", "head", "token")

    def test_no_files_fails_closed(self):
        with patch.object(policy, "get_json", side_effect=self.mock_api([])):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "old-base", "head", "token")

    def test_truncated_tree_fails_closed(self):
        calls = self.mock_api([changed("README.md", "added")])
        calls[3]["truncated"] = True
        with patch.object(policy, "get_json", side_effect=calls):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "old-base", "head", "token")

    def test_base_moves_during_verification_fails_closed(self):
        with patch.object(policy, "get_json", side_effect=self.mock_api(
            [changed("README.md", "added")], final_sha="new-current"
        )):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "old-base", "head", "token")

    def test_nonmain_base_fails_closed(self):
        with patch.object(policy, "get_json", side_effect=[
            {"base": {"sha": "old-base", "ref": "other"}, "head": {"sha": "head"}}
        ]):
            with self.assertRaises(ValueError):
                policy.verify_pr("owner/repo", 1, "old-base", "head", "token")


if __name__ == "__main__":
    unittest.main()
