#!/usr/bin/env python3
"""Read-only PR file policy. Run only from trusted default-branch checkout."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

LOCKED = frozenset({
    ".github/workflows/trusted-safety.yml",
    "scripts/trusted_pr_policy.py",
})
ALLOWED_STATUSES = frozenset({"added", "modified", "removed", "renamed", "copied", "changed"})


def is_protected(path: str) -> bool:
    parts = path.split("/")
    return "raw" in parts or parts[-2:] == ["_meta", "LOG.md"] or path in LOCKED


def evaluate_files(
    files: list[dict[str, Any]], existing_base_paths: frozenset[str] = frozenset()
) -> list[str]:
    errors: list[str] = []
    for entry in files:
        name, status = entry.get("filename"), entry.get("status")
        if not isinstance(name, str) or not name or not isinstance(status, str):
            raise ValueError("Malformed file entry")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unknown GitHub file status: {status!r}")
        if status in {"removed", "renamed", "copied", "changed"}:
            errors.append(f"Forbidden operation ({status}): {name}")
        if is_protected(name) and (status != "added" or name in existing_base_paths):
            errors.append(f"Protected content already exists on current base or was modified: {name}")
        if status == "renamed":
            previous = entry.get("previous_filename")
            if not isinstance(previous, str) or not previous:
                raise ValueError("Rename missing previous_filename")
            parts = previous.split("/")
            if "raw" in parts or parts[-2:] == ["_meta", "LOG.md"] or previous in LOCKED:
                errors.append(f"Protected existing path renamed: {previous}")
    return errors


def get_json(url: str, token: str) -> Any:
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "llm-wiki-toolkit-trusted-policy",
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def current_base_tree(repository: str, ref: str, token: str) -> tuple[str, frozenset[str]]:
    """Read a single base snapshot; fail closed if the GitHub tree is incomplete."""
    if ref != "main":
        raise ValueError("Only protected main can be checked")
    url = f"https://api.github.com/repos/{repository}"
    branch = get_json(f"{url}/git/ref/heads/{ref}", token)
    sha = branch["object"]["sha"]
    if not isinstance(sha, str) or len(sha) != 40:
        raise ValueError("Invalid current base SHA")
    commit = get_json(f"{url}/git/commits/{sha}", token)
    tree_sha = commit["tree"]["sha"]
    tree = get_json(f"{url}/git/trees/{tree_sha}?recursive=1", token)
    if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
        raise ValueError("Cannot inspect complete current base tree")
    existing: set[str] = set()
    for item in tree["tree"]:
        path = item["path"]
        if not isinstance(path, str) or not path:
            raise ValueError("Malformed current base tree")
        if item["type"] in ("blob", "commit"):
            existing.add(path)
    return sha, frozenset(existing)


def verify_pr(repository: str, number: int, base_sha: str, head_sha: str, token: str) -> list[str]:
    if not repository or number < 1 or not token:
        raise ValueError("Missing repository, PR number or authentication")
    prefix = f"https://api.github.com/repos/{repository}/pulls/{number}"
    pr = get_json(prefix, token)
    if pr["base"]["sha"] != base_sha or pr["head"]["sha"] != head_sha:
        raise ValueError("PR head/base changed; rerun on current commit")
    ref = pr["base"]["ref"]
    current_sha, base_paths = current_base_tree(repository, ref, token)
    all_files: list[dict[str, Any]] = []
    for page in range(1, 31):
        batch = get_json(f"{prefix}/files?per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError("Malformed GitHub files response")
        all_files.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError("At least 3000 files; cannot verify complete diff")
    if len(all_files) != pr["changed_files"]:
        raise ValueError("File count mismatch; cannot verify complete diff")
    if not all_files:
        raise ValueError("Empty file list; refusing uncertain PR state")
    # Avoid approving a mixed snapshot if the branch or PR moved during pagination.
    final_pr = get_json(prefix, token)
    final_ref = get_json(f"https://api.github.com/repos/{repository}/git/ref/heads/{ref}", token)
    if (final_pr["base"]["sha"] != base_sha or
        final_pr["head"]["sha"] != head_sha or
        final_ref["object"]["sha"] != current_sha):
        raise ValueError("PR or current base moved during verification")
    return evaluate_files(all_files, base_paths)


def main() -> int:
    try:
        violations = verify_pr(
            os.environ["GITHUB_REPOSITORY"],
            int(os.environ["PR_NUMBER"]),
            os.environ["PR_BASE_SHA"],
            os.environ["PR_HEAD_SHA"],
            os.environ["GITHUB_TOKEN"],
        )
        for violation in violations:
            print("TRUSTED-SAFETY: " + violation, file=sys.stderr)
        return 1 if violations else 0
    except (KeyError, ValueError, TypeError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print("TRUSTED-SAFETY: verification failed closed: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
