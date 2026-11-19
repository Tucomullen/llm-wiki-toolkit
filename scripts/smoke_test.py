"""End-to-end smoke test against an installed wikikit package (disposable wiki)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cwd: Path, *args: str, expected: int = 0) -> str:
    p = subprocess.run([sys.executable, "-m", "wikikit", *args], cwd=cwd,
                       text=True, capture_output=True, encoding="utf-8")
    if p.returncode != expected:
        raise RuntimeError(f"wikikit {args} -> {p.returncode}, expected {expected}\n{p.stdout}\n{p.stderr}")
    return p.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wikikit-smoke-") as d:
        temp = Path(d)
        wiki = temp / "demo"
        shutil.copytree(ROOT / "examples" / "demo-wiki", wiki)
        run(wiki, "split-index", "_meta/INDEX.md")
        run(wiki, "verify", "--fail-on-broken")
        run(wiki, "search", "index")
        result = run(wiki, "search", "query", "mulch")
        if "Mulching Guide" not in result:
            raise AssertionError("Expected demo document absent from search results")
        entry = wiki / "_meta" / "_raw_pending" / "entry.md"
        entry.write_text("## [2026-11-19] NOTE | Smoke test\nTest entry.\n", encoding="utf-8")
        run(wiki, "log", "append", str(entry))
        if "Smoke test" not in (wiki / "_meta" / "LOG.md").read_text(encoding="utf-8"):
            raise AssertionError("Append-only log entry not found")
        src = wiki / "_meta" / "_raw_pending" / "unique-smoke.txt"
        src.write_text("new disposable sample", encoding="utf-8")
        run(wiki, "raw", "save", str(src))
        if not (wiki / "raw" / "unique-smoke.txt").exists():
            raise AssertionError("Raw source not saved")
        src.write_text("must not overwrite", encoding="utf-8")
        run(wiki, "raw", "save", str(src), expected=2)
        if (wiki / "raw" / "unique-smoke.txt").read_text(encoding="utf-8") != "new disposable sample":
            raise AssertionError("Raw source was overwritten")
    print("Smoke test PASS: split, verify, search, append, create-only raw")
    return 0


if __name__ == "__main__":
    sys.exit(main())
