# llm-wiki-toolkit

A small, dependency-free kit for keeping a **Markdown knowledge base** that AI agents (Claude Code, Codex, and others) read and write, **without a vector database**.

- **Two-level index**: a tiny master index routes the agent to small sub-indices, so it never loads one giant file.
- **Local full-text search**: SQLite FTS5 over your pages and source documents, incremental, no server.
- **Safe writes**: the log is append-only and `raw/` is create-only, both enforced by checksums, not by hope.
- **Integrity verifier**: `wikikit verify` finds pages without frontmatter, broken links, stale counts and unindexed pages.

Python 3.10+, standard library only in the core. Works on Windows, macOS and Linux. (English | [Español](README.es.md))

## The problem

When an agent maintains a wiki over months, four things go wrong: the index grows until it eats the context window, the agent greps blindly, it "tidies" files it must never touch (the source documents, the audit log), and links and counts silently rot. `wikikit` fixes each with a boring, testable tool.

## Install

```bash
pip install .            # core, no third-party dependencies
pip install .[docs]      # adds .docx / .pdf / .pptx text extraction (python-docx, pypdf, python-pptx)
```

Check it works: `wikikit --version`.

## Quickstart (5 minutes, with the demo)

The repository ships a fictional garden-club wiki in `examples/demo-wiki/` with a monolithic index.

```bash
cp -r examples/demo-wiki /tmp/garden && cd /tmp/garden      # any scratch folder

wikikit split-index _meta/INDEX.md --dry-run   # preview: what goes where
wikikit split-index _meta/INDEX.md             # split (backup kept in _meta/_archive/)
wikikit verify --fail-on-broken                # 0 BROKEN, 0 WARN

wikikit search index                           # build the local search index
wikikit search query "mulch" -n 3              # ranked results with snippets
wikikit search query "marigolds zeppelin" --any --json

# append to the log safely
printf '## [2026-05-01] NOTE | Tried wikikit\nIt works.\n' > _meta/entry.md
wikikit log append _meta/entry.md

# add a source document without ever overwriting
printf 'new notes' > _meta/_raw_pending/notes.txt
wikikit raw save _meta/_raw_pending/notes.txt
```

`examples/demo-wiki-after/` is the expected result of the split; `examples/demo-index-before/INDEX.md` is the original monolith.

Start your own wiki with `wikikit init my-wiki`.

## Layout

```
wiki/                 pages (Markdown, YAML frontmatter, file name = H1)
raw/                  immutable sources (create-only)
_meta/INDEX.md        master index: <!-- KB-COUNT: N --> and a table of sub-indices
_meta/index/*.md      sub-indices: "- [[Title]] — description"
_meta/index/_HISTORY.md  changelog blocks moved out of the master (never read in queries)
_meta/LOG.md          append-only operation log
_meta/_raw_pending/   staging folder for `wikikit raw save`
wikikit.toml          optional configuration
```

## Command reference

Global option: `--root DIR` (default: nearest parent folder containing `wikikit.toml`, else the current folder). Give it before the subcommand.

| Command | What it does |
|---|---|
| `wikikit init [DIR]` | Create the minimal structure, a commented `wikikit.toml` and agent templates. Never overwrites. |
| `wikikit split-index INDEX.md [--dry-run] [--force]` | Split a monolithic index (one sub-index per `##`, or per `###` in sections larger than the threshold). History/changelog sections go to `_HISTORY.md`. Backs up the original and **aborts without writing** if any `[[link]]` or catalog line would be lost. |
| `wikikit search index [--full]` | Build or incrementally update the FTS5 index (mtime + size; deletions removed). |
| `wikikit search query "text" [-n 10] [--source X] [--project X] [--any] [--fts] [--per-file 2] [--json]` | Default: terms are quoted and joined with AND. `--any` = OR. `--fts` = raw FTS5 syntax (clear error if invalid). |
| `wikikit search stats` | Files, chunks, DB location, skipped files with reasons. |
| `wikikit log append ENTRY.md` | Requires header `## [YYYY-MM-DD] TYPE | title`; rejects duplicates; appends; verifies via SHA-256 that old content is unchanged and the size grew by exactly the added bytes; archives the entry file. |
| `wikikit raw save FILE [--name NAME]` | Copies from `_meta/_raw_pending/` into `raw/` only if the name is free; rejects separators and `..`; verifies SHA-256; removes the original. |
| `wikikit verify [--fail-on-broken] [--json]` | BROKEN: no frontmatter, broken `[[link]]` (frontmatter aliases honoured), `KB-COUNT` mismatch, page in no sub-index, sub-index entry without file. WARN: file name ≠ H1, `title` ≠ H1. Exit 1 with `--fail-on-broken` if anything is BROKEN. |

Search details: chunks of about 1,200–1,800 characters cut at paragraph/heading boundaries; bm25 weights title=1, heading=2, body=1; tokenizer `unicode61 remove_diacritics 2` with `prefix='3'`. Formats: `.md .txt .vtt .srt .eml .html` always; `.docx .pdf .pptx` with the `docs` extra (otherwise reported as skipped). `node_modules .git .venv __pycache__ dist build tmp` are excluded. On Windows, cloud-only placeholder files (recall-on-data-access / offline attributes) are never opened; they are listed as skipped. The database lives in your user cache directory (`%LOCALAPPDATA%\wikikit\<hash>.sqlite` or `~/.cache/wikikit/<hash>.sqlite`), **outside** synced folders, because SQLite files and cloud sync do not mix.

### Configuration

All keys are optional. See the commented file that `wikikit init` writes:

```toml
wiki_dir = "wiki"
raw_dir = "raw"
meta_dir = "_meta"
index_dir = "_meta/index"
[search]
sources = ["wiki", "raw"]
snippet_marks = ["**", "**"]     # default is "«" and "»"
[split]
threshold = 150
history_patterns = ["\\bhistory\\b", "\\bchangelog\\b"]
```

## Why a two-level index plus FTS5 is enough (and when it is not)

An agent does not need embeddings to find the right page in a curated wiki: pages have descriptive titles, the index is written for the agent, and keyword search over a few thousand documents is instant and exact.

- **Index in two levels.** The master index stays around 3 KB and only names the topics. The agent opens the one or two sub-indices that matter, each a few hundred lines. Cost per query stays flat as the wiki grows.
- **FTS5 for facts.** Exact terms (codes, names, numbers, dates) are where vectors are weakest and keyword search is strongest. bm25 with a heading boost ranks well on curated text. It is deterministic, offline, and its results are auditable.
- **Where it holds.** Up to a few thousand documents (tens of thousands of chunks) the index builds in seconds and queries return in milliseconds.
- **When to add vectors.** Consider embeddings when (a) users query in vocabulary the pages do not contain (paraphrase, other languages), (b) the corpus is far beyond tens of thousands of pages, or (c) pages are long, unstructured dumps with no useful titles. Even then, keep this toolkit: use FTS5 for exact lookups and the index for navigation, and add vectors as a third path. A `--json` output makes it easy to feed a re-ranker.

## Using it with Claude Code and other agents

1. `wikikit init` writes `AGENTS.md` (read by Codex and many agents) and `CLAUDE.md` (Claude Code). Both tell the agent to read the master index first, search before grepping, and log/save only through `wikikit`.
2. Copy `templates/claude-settings.example.json` to `.claude/settings.json`. It **denies** `Edit(raw/**)` and `Edit(_meta/LOG.md)` and **allows** the `wikikit` commands, so the locks are enforced by the harness, not by the prompt. A denial on those paths is the lock working, not an error.
3. Any agent that can run shell commands can use the CLI. Use `--json` for machine-readable output.
4. End every agent session with `wikikit verify --fail-on-broken`.

## FAQ

**Does it need internet or an API key?** No. Everything is local.

**Does it change my pages?** No. Only `split-index` rewrites the index file (after a backup), `log append` appends, `raw save` creates, `init` creates missing files.

**Why can't I overwrite a file in `raw/`?** By design: sources are evidence. Save the new version under a new name.

**Why is `KB-COUNT` in the master?** A cheap tripwire. If the number of pages on disk differs, someone added or deleted a page without updating the index, and `verify` says so.

**Obsidian compatible?** Yes: `[[wikilinks]]`, frontmatter `aliases`, and file name = title.

**Why does `verify` print BROKEN/WARN?** Severity labels are kept stable for scripts: BROKEN = broken, WARN = could be improved.

**SQLite without FTS5?** Almost every Python build ships FTS5. If yours does not, `search` prints a clear error.

## Development

```bash
python -m unittest discover -s tests -v     # no dependencies needed
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [ROADMAP.md](ROADMAP.md) (several "good first issue" items).

## License

MIT. See [LICENSE](LICENSE).
