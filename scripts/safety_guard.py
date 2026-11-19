#!/usr/bin/env python3
"""Block accidental history/source modifications and all deletions in git changes.

Client git hooks are optional; CI repeats the checks on pull requests.
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def protected(path: str) -> bool:
    parts = path.split("/")
    return ("raw" in parts or (len(parts) >= 2 and parts[-2:] == ["_meta", "LOG.md"]))


def evaluate(diff: str) -> list[str]:
    errors: list[str] = []
    for line in diff.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        code = fields[0][0]
        paths = fields[1:]
        if code == "D":
            errors.append(f"Deletion forbidden: {paths[0]}")
        elif code in ("R", "C"):
            errors.append(f"Rename/copy needs manual approval: {', '.join(paths)}")
        elif code != "A" and any(protected(p) for p in paths):
            errors.append(f"Protected existing source or history modified: {', '.join(paths)}")
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--staged", action="store_true")
    g.add_argument("--compare", nargs=2, metavar=("BASE", "HEAD"))
    g.add_argument("--pre-push", action="store_true")
    args = p.parse_args()
    try:
        if args.staged:
            diff = git("diff", "--cached", "--name-status", "--no-renames", "--diff-filter=ACDMRT")
            problems = evaluate(diff)
        elif args.compare:
            diff = git("diff", "--name-status", "--no-renames", *args.compare)
            problems = evaluate(diff)
        else:
            problems = []
            for line in sys.stdin:
                fields = line.split()
                if len(fields) != 4:
                    continue
                local_ref, local_sha, remote_ref, remote_sha = fields
                if remote_ref == "refs/heads/main":
                    problems.append("Direct push to main forbidden: use a reviewed pull request")
                if local_sha != "0" * 40 and remote_sha != "0" * 40:
                    problems += evaluate(git("diff", "--name-status", "--no-renames", remote_sha, local_sha))
        for problem in problems:
            print(f"SAFETY GUARD: {problem}", file=sys.stderr)
        return 1 if problems else 0
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"SAFETY GUARD: cannot verify changes: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
