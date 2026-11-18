"""`wikikit init`: create the minimal wiki structure."""
from __future__ import annotations

from pathlib import Path

from .config import CONFIG_NAME, Config

TOML = '''# wikikit configuration. All values shown are the defaults.
wiki_dir = "wiki"
raw_dir = "raw"
meta_dir = "_meta"
index_dir = "_meta/index"
master_index = "_meta/INDEX.md"
history_file = "_meta/index/_HISTORY.md"
log_file = "_meta/LOG.md"
log_archive_dir = "_meta/_archive/log_applied"
raw_pending_dir = "_meta/_raw_pending"

[search]
# Directories (relative to this file) to index. The first sub-folder under each is the "project".
sources = ["wiki", "raw"]
exclude_dirs = ["node_modules", ".git", ".venv", "__pycache__", "dist", "build", "tmp"]
# Empty = user cache dir (%LOCALAPPDATA%\\wikikit on Windows, ~/.cache/wikikit elsewhere).
db_path = ""
snippet_marks = ["\\u00ab", "\\u00bb"]
chunk_min = 1200
chunk_max = 1800

[split]
# Sections with more entries than this are split by "###" sub-sections.
threshold = 150
# Headings matching these regexes are moved to the history file.
history_patterns = ["\\\\bhistory\\\\b", "\\\\bchangelog\\\\b", "\\\\bchange log\\\\b", "\\\\bupdate log\\\\b"]

[verify]
infra_files = ["CLAUDE.md", "AGENTS.md"]
'''

MASTER = """# Index

<!-- KB-COUNT: 0 -->

| Path | Entries in index | Files on disk | Sub-index |
|------|-----------------:|--------------:|-----------|
"""


def _template(name: str) -> str:
    return (Path(__file__).parent / "templates" / name).read_text(encoding="utf-8")


def cmd_init(cfg: Config) -> int:
    root = cfg.root
    root.mkdir(parents=True, exist_ok=True)
    for d in (cfg.wiki_dir, cfg.raw_dir, cfg.index_dir, cfg.raw_pending_dir):
        cfg.path(d).mkdir(parents=True, exist_ok=True)
    files = {
        CONFIG_NAME: TOML,
        cfg.master_index: MASTER,
        cfg.log_file: "# Log\n\nAppend-only. Use `wikikit log append`.\n",
        "AGENTS.md": _template("AGENTS.md"),
        "CLAUDE.md": _template("CLAUDE.md"),
        cfg.meta_dir + "/claude-settings.example.json": _template("claude-settings.example.json"),
    }
    for rel, content in files.items():
        p = cfg.path(rel)
        if p.exists():
            print(f"  kept   {rel} (already exists)")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
        print(f"  wrote  {rel}")
    print(f"Initialised wiki at {root}")
    return 0
