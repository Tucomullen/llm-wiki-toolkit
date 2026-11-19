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


def evaluate_files(files: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for entry in files:
        name, status = entry.get("filename"), entry.get("status")
        if not isinstance(name, str) or not name or not isinstance(status, str):
            raise ValueError("Malformed file entry")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unknown GitHub file status: {status!r}")
        if status in {"removed", "renamed", "copied", "changed"}:
            errors.append(f"Forbidden operation ({status}): {name}")
        segments = name.split("/")
        protected = "raw" in segments or segments[-2:] == ["_meta", "LOG.md"]
        if protected and status != "added":
            errors.append(f"Existing raw/history content modified: {name}")
        if name in LOCKED and status != "added":
            errors.append(f"Trusted security configuration modified: {name}")
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


def verify_pr(repository: str, number: int, base_sha: str, head_sha: str, token: str) -> list[str]:
    if not repository or number < 1 or not token:
        raise ValueError("Missing repository, PR number or authentication")
    prefix = f"https://api.github.com/repos/{repository}/pulls/{number}"
    pr = get_json(prefix, token)
    if pr["base"]["sha"] != base_sha or pr["head"]["sha"] != head_sha:
        raise ValueError("PR head/base changed; rerun on current commit")
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
    return evaluate_files(all_files)


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
