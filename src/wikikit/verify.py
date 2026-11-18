"""`wikikit verify`: integrity invariants for the wiki."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .util import (CATALOG_RE, KBCOUNT_RE, LINK_RE, first_h1, norm_target, parse_frontmatter,
                   read_text, strip_code)

BROKEN = "BROKEN"
IMPROVABLE = "WARN"


@dataclass
class Page:
    rel: str
    stem: str
    meta: dict | None
    h1: str | None
    links: set = field(default_factory=set)
    aliases: list = field(default_factory=list)

    def names(self) -> set:
        return {norm_target(self.stem)} | {norm_target(a) for a in self.aliases}


def collect_pages(cfg: Config) -> list:
    wiki = cfg.path(cfg.wiki_dir)
    infra = {n.lower() for n in cfg.infra_files}
    pages = []
    if not wiki.is_dir():
        return pages
    for dirpath, dirnames, filenames in os.walk(wiki):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in cfg.exclude_dirs)
        for fn in sorted(filenames):
            if not fn.lower().endswith(".md") or fn.lower() in infra:
                continue
            p = Path(dirpath) / fn
            text = read_text(p)
            meta, consumed = parse_frontmatter(text)
            body_lines = text.splitlines()[consumed:]
            aliases = []
            if meta:
                a = meta.get("aliases", [])
                aliases = a if isinstance(a, list) else [a]
            links = {m.group(1).strip() for m in LINK_RE.finditer(strip_code("\n".join(body_lines)))}
            pages.append(Page(p.relative_to(cfg.root).as_posix(), p.stem, meta, first_h1(body_lines),
                              links, [x for x in aliases if x]))
    return pages


def resolvable_names(cfg: Config, pages: list) -> set:
    names = set()
    for p in pages:
        names |= p.names()
    for d in (cfg.wiki_dir, cfg.raw_dir):
        base = cfg.path(d)
        if base.is_dir():
            for _, _, fns in os.walk(base):
                for fn in fns:
                    names.add(fn.casefold())
    return names


def _resolves(target: str, names: set) -> bool:
    t = target.strip().replace("\\", "/").rsplit("/", 1)[-1]
    return t.casefold() in names or norm_target(t) in names


def subindex_entries(cfg: Config) -> list:
    """Return [(relpath, target)] for catalog entries of every sub-index (files starting with _ skipped)."""
    out = []
    idx = cfg.path(cfg.index_dir)
    if not idx.is_dir():
        return out
    for f in sorted(idx.glob("*.md")):
        if f.name.startswith("_"):
            continue
        for line in read_text(f).splitlines():
            m = CATALOG_RE.match(line)
            if m:
                out.append((f.relative_to(cfg.root).as_posix(), m.group(1).strip()))
    return out


def run_checks(cfg: Config) -> dict:
    pages = collect_pages(cfg)
    issues = []

    def add(sev, code, path, msg):
        issues.append({"severity": sev, "code": code, "path": path, "message": msg})

    names = resolvable_names(cfg, pages)
    for p in pages:
        if p.meta is None:
            add(BROKEN, "no-frontmatter", p.rel, "page has no YAML frontmatter")
        for t in sorted(p.links):
            if not _resolves(t, names):
                add(BROKEN, "broken-link", p.rel, f"link [[{t}]] points to a page that does not exist")
        if p.h1 is None:
            add(IMPROVABLE, "no-h1", p.rel, "page has no H1 heading")
        else:
            if norm_target(p.stem) != norm_target(p.h1) or p.stem != p.h1:
                add(IMPROVABLE, "filename-h1", p.rel, f"file name '{p.stem}' differs from H1 '{p.h1}'")
            title = (p.meta or {}).get("title")
            if isinstance(title, str) and title != p.h1:
                add(IMPROVABLE, "title-h1", p.rel, f"frontmatter title '{title}' differs from H1 '{p.h1}'")

    master = cfg.path(cfg.master_index)
    if not master.is_file():
        add(BROKEN, "no-master", cfg.master_index, "master index not found")
    else:
        m = KBCOUNT_RE.search(read_text(master))
        if not m:
            add(BROKEN, "kb-count-missing", cfg.master_index, "KB-COUNT marker not found")
        elif int(m.group(1)) != len(pages):
            add(BROKEN, "kb-count-mismatch", cfg.master_index,
                f"KB-COUNT is {m.group(1)} but there are {len(pages)} pages on disk")

    entries = subindex_entries(cfg)
    targets = {norm_target(t) for _, t in entries}
    for p in pages:
        if not (p.names() & targets):
            add(BROKEN, "not-indexed", p.rel, "page has no entry in any sub-index")
    for rel, t in entries:
        if not _resolves(t, names):
            add(BROKEN, "entry-without-file", rel, f"entry [[{t}]] has no file")

    summary = {"pages": len(pages), "broken": sum(i["severity"] == BROKEN for i in issues),
               "improvable": sum(i["severity"] == IMPROVABLE for i in issues)}
    return {"summary": summary, "issues": issues}


def format_report(result: dict) -> str:
    lines = []
    for sev in (BROKEN, IMPROVABLE):
        group = [i for i in result["issues"] if i["severity"] == sev]
        lines.append(f"{sev} ({len(group)})")
        for i in group:
            lines.append(f"  [{i['code']}] {i['path']}: {i['message']}")
    s = result["summary"]
    lines.append(f"\n{s['pages']} pages checked: {s['broken']} {BROKEN}, {s['improvable']} {IMPROVABLE}.")
    return "\n".join(lines)


def cmd_verify(cfg: Config, fail_on_broken: bool, as_json: bool) -> int:
    result = run_checks(cfg)
    print(json.dumps(result, indent=2, ensure_ascii=False) if as_json else format_report(result))
    return 1 if fail_on_broken and result["summary"]["broken"] else 0
