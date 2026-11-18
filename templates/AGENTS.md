# Agent instructions for this wiki

This directory is a Markdown knowledge base maintained with `wikikit`.

## Reading

1. Read the master index `_meta/INDEX.md` (small). It lists sub-indices in `_meta/index/`.
2. Open only the sub-indices relevant to the question. Never read `_meta/index/_HISTORY.md`.
3. For concrete facts, search first: `wikikit search index` (once, then incremental) and
   `wikikit search query "term" [--project NAME] [--json]`. Prefer it to grep.
4. Cite the page or source file for every claim. If the wiki does not say it, say so.

## Writing

- Every page in `wiki/` starts with YAML frontmatter (`title`, `aliases`, `date`, `tags`, `status`).
- File name = H1 title exactly. Link pages with `[[Page Title]]`.
- Add each new page as a line `- [[Title]] — description` to the right sub-index in `_meta/index/`,
  then update the `KB-COUNT` marker and table row in `_meta/INDEX.md`.
- Log every operation: write the entry to a temporary file with the header
  `## [YYYY-MM-DD] TYPE | title`, then run `wikikit log append <file>`.
  Never edit `_meta/LOG.md` by hand.
- New source documents: put them in `_meta/_raw_pending/`, then run `wikikit raw save <file>`.
  Never edit, move or delete anything in `raw/`.
- Before finishing, run `wikikit verify`. Fix every BROKEN item.

## Hard rules

- `raw/` is immutable. `_meta/LOG.md` is append-only.
- Do not invent facts. Mark inferences as such.
