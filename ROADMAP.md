# Roadmap

Items marked **good first issue** are small, self-contained and have clear acceptance criteria. Ask in the issue before starting, so nobody duplicates work.

## Good first issues

1. **Export search results as JSON Lines** (`--jsonl`): one result object per line, for streaming into other tools. Test: output parses line by line.
2. **`.odt` support** in `extract.py` (zip + `content.xml`, standard library only). Test with a tiny hand-built fixture.
3. **Pre-commit hook** that runs `wikikit verify --fail-on-broken`: ship `.pre-commit-hooks.yaml` and a documented plain `git` hook script.
4. **`wikikit verify --only CODE`**: filter by issue code (`broken-link`, `not-indexed`, ...) to make CI output focused.
5. **Colour output** for `verify` and `search query` when stdout is a TTY, with `--no-color` and `NO_COLOR` support.
6. **`.rst` and `.org` extractors** (plain-text level, headings preserved) with tests.
7. **`wikikit search query --open N`**: print the full text of result N (by path and chunk location).
8. **Shell completions** (bash/zsh/fish) generated from the argparse definition.
9. **Orphan report**: `verify --report orphans` listing pages that nothing links to (informational, not BROKEN).
10. **Docs: recipes page** for Codex, Gemini CLI and Cursor (where to put `AGENTS.md`, how to lock `raw/`).

## Later

- **MCP server** exposing `search query`, `verify` and read-only index navigation to MCP clients.
- Optional **vector re-ranking** plugin (extra dependency, off by default) that re-ranks FTS5 candidates.
- **Index staleness hint**: `search query` warns when files changed since the last `search index`.
- Multi-wiki search (`--root` repeated) with results labelled per wiki.
- Windows long-path handling audit.
