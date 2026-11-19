# First run: from installation to a useful result

This guide requires **Python 3.10+**. Commands below work in **Windows PowerShell, macOS and Linux** (use `python3` instead of `python` if that is how Python is installed). No API key, server, or agent subscription is needed.

## Install without cloning the repository

Create and activate a virtual environment (recommended). For a shell-independent installation, use a Python interpreter directly:

```console
python -m pip install "git+https://github.com/Tucomullen/llm-wiki-toolkit.git"
python -m wikikit --version
```

This command requires Git installed and network access. There is **no PyPI release yet**. Installing from a local checkout with `python -m pip install .` is also supported. A future PyPI release may remove the Git requirement.

## Start a fresh wiki

From any working directory:

```console
python -m wikikit init first-wiki
python -m wikikit --root first-wiki verify --fail-on-broken
```

The second command should report **0 BROKEN** on the newly initialized, empty wiki.

Create `first-wiki/wiki/First Note.md` using any text editor with this exact content:

```markdown
---
title: First Note
---

# First Note

Garden compost improves soil structure.
```

Create `first-wiki/_meta/index/notes.md`:

```markdown
# Notes

- [[First Note]] — A practical note about compost.
```

Edit `first-wiki/_meta/INDEX.md` so it contains:

```markdown
# Index

<!-- KB-COUNT: 1 -->

| Path | Entries in index | Files on disk | Sub-index |
|------|-----------------:|--------------:|-----------|
| Notes | 1 | 1 | [notes.md](index/notes.md) |
```

Now index the content, search and check consistency:

```console
python -m wikikit --root first-wiki search index
python -m wikikit --root first-wiki search query "compost" --json
python -m wikikit --root first-wiki verify --fail-on-broken
```

Expected: the JSON query contains `wiki/First Note.md`, and verification reports **1 page, 0 BROKEN, 0 WARN**.

To add original reference material, put a file directly in `first-wiki/_meta/_raw_pending/`. Then from your working directory run:

```console
python -m wikikit --root first-wiki raw save first-wiki/_meta/_raw_pending/source.txt
```

`raw save` is intentionally **create-only**: a second save under the same name must fail instead of overwriting the first one. Note that the CLI resolves the staged file path relative to the **current working directory**, not `--root`.

## Common first-run problems

| Symptom | Explanation / fix |
|---|---|
| `No module named wikikit` | Verify the installation uses the same Python interpreter: `python -m pip --version` and `python -m wikikit --version`. |
| `git executable not found` | Git is required for install-from-GitHub. Alternatively download GitHub's **Source code ZIP**, unpack it, and run `python -m pip install .` from the extracted project directory. |
| `no index found` | Run `python -m wikikit --root first-wiki search index` before querying. |
| `not-indexed` or `kb-count-mismatch` | Every Markdown page needs a matching sub-index entry and the master index count must reflect the number of pages. `init` does **not** automatically register pages added manually. |
| `no-frontmatter` | Start each page with `---`, a `title:` entry, and a closing `---`. |
| `raw/... already exists` | Expected safety check: choose another source filename; existing originals cannot be overwritten. |
| Search fails with `FTS5` | Use a Python distribution whose SQLite build includes FTS5. |
| `wikikit` command not found | Use `python -m wikikit` to avoid shell PATH issues. |

## How an AI agent uses the wiki

`init` adds `AGENTS.md` and `CLAUDE.md` at the wiki root. Open **that directory** in your agent. The agent should read `_meta/INDEX.md`, follow the appropriate sub-index, run `wikikit search index` and `wikikit search query` for facts, and finish with `wikikit verify --fail-on-broken`. Those actions can be performed without an agent, as shown above.

**Important:** `split-index` converts a **pre-existing monolithic catalog** into sub-indices; do not run it on a freshly initialized master index. For the garden-club demo, download the source repository and use the separate instructions in the README. This first-run guide intentionally avoids shell-specific copy commands.

