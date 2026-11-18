"""Shared test helpers (standard library only)."""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wikikit.cli import main  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "examples" / "demo-wiki"
DEMO_AFTER = REPO / "examples" / "demo-wiki-after"


def run(*argv, root=None):
    """Run the CLI in-process. Returns (exit_code, stdout)."""
    args = list(argv)
    if root is not None:
        args = ["--root", str(root)] + args
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(args)
    return code, buf.getvalue()


class WikiCase(unittest.TestCase):
    """Creates a temp wiki root (with a private search DB) for each test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wikikit-test-"))
        self.root = self.tmp / "wiki-root"
        self.root.mkdir()
        self.db = self.tmp / "search.sqlite"
        (self.root / "wikikit.toml").write_text(
            f'[search]\ndb_path = "{self.db.as_posix()}"\n[split]\nthreshold = 4\n', encoding="utf-8")
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def write(self, rel, text="", binary=None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if binary is not None:
            p.write_bytes(binary)
        else:
            p.write_text(text, encoding="utf-8", newline="\n")
        return p

    def cli(self, *argv):
        return run(*argv, root=self.root)

    def copy_demo(self, src=DEMO):
        shutil.rmtree(self.root)
        shutil.copytree(src, self.root)
        (self.root / "wikikit.toml").write_text(
            f'[search]\ndb_path = "{self.db.as_posix()}"\n[split]\nthreshold = 4\n', encoding="utf-8")


def page(title, body="Some text.", extra_fm="", links=""):
    return f"---\ntitle: {title}\n{extra_fm}---\n\n# {title}\n\n{body} {links}\n"
