"""Cross-platform first-user smoke test against the installed Python package.

Does not import the local src tree. Uses temporary files only and tests negative paths.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args: str, expected: int = 0) -> str:
    cmd = [sys.executable, "-m", "wikikit", *map(str, args)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != expected:
        raise AssertionError(f"{cmd!r}: expected {expected}, got {p.returncode}\nstdout: {p.stdout}\nstderr: {p.stderr}")
    return p.stdout


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="wikikit-first-user-") as temp:
        root = Path(temp) / "first-wiki"
        assert "Initialised wiki" in run("init", root)
        assert "0 BROKEN" in run("--root", root, "verify", "--fail-on-broken")
        assert "no index found" in run("--root", root, "search", "query", "compost", expected=2)

        (root / "wiki" / "First Note.md").write_text(
            "---\ntitle: First Note\n---\n\n# First Note\n\nGarden compost improves soil structure.\n",
            encoding="utf-8",
        )
        assert "not-indexed" in run("--root", root, "verify", "--fail-on-broken", expected=1)
        (root / "_meta" / "index" / "notes.md").write_text(
            "# Notes\n\n- [[First Note]] — A practical note about compost.\n", encoding="utf-8"
        )
        (root / "_meta" / "INDEX.md").write_text(
            "# Index\n\n<!-- KB-COUNT: 1 -->\n\n"
            "| Path | Entries in index | Files on disk | Sub-index |\n"
            "|------|-----------------:|--------------:|-----------|\n"
            "| Notes | 1 | 1 | [notes.md](index/notes.md) |\n", encoding="utf-8"
        )
        run("--root", root, "search", "index")
        results = json.loads(run("--root", root, "search", "query", "compost", "--json"))
        assert results and results[0]["path"] == "wiki/First Note.md", results
        assert "0 BROKEN" in run("--root", root, "verify", "--fail-on-broken")
        pending = root / "_meta" / "_raw_pending" / "source.txt"
        pending.write_text("First user source notes", encoding="utf-8")
        assert "Saved raw/source.txt" in run("--root", root, "raw", "save", pending)
        assert (root / "raw" / "source.txt").read_text(encoding="utf-8") == "First user source notes"
        pending.write_text("changed", encoding="utf-8")
        assert "already exists" in run("--root", root, "raw", "save", pending, expected=2)
        assert (root / "raw" / "source.txt").read_text(encoding="utf-8") == "First user source notes"
        assert pending.read_text(encoding="utf-8") == "changed"
    print("PASS: first-user journey (init, broken detection, index, query, verify, raw safety)")


if __name__ == "__main__":
    main()
