"""`wikikit split-index`: split a monolithic index into a small master + sub-indices."""
from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .util import (CATALOG_RE, FENCE_RE, HEADING_RE, LINK_RE, link_targets, norm_target, read_text,
                   slugify)
from .verify import collect_pages, resolvable_names


class SplitError(Exception):
    pass


class LinkLost(SplitError):
    pass


@dataclass
class Piece:
    name: str
    lines: list
    history: bool = False
    slug: str = ""

    @property
    def entries(self) -> list:
        out = []
        for line in self.lines:
            m = CATALOG_RE.match(line)
            if m:
                out.append(m.group(1).strip())
        return out


@dataclass
class Plan:
    title: str
    intro: list
    pieces: list = field(default_factory=list)


def _is_history(heading: str, patterns) -> bool:
    return any(re.search(p, heading, re.I) for p in patterns)


def _split_by_level(lines, level):
    """Split lines on headings of exactly `level` (outside code fences). Returns (before, [(heading, body)])."""
    before, blocks, fence = [], [], False
    cur = None
    for line in lines:
        if FENCE_RE.match(line):
            fence = not fence
        m = None if fence else HEADING_RE.match(line)
        if m and len(m.group(1)) == level:
            cur = (m.group(2), [])
            blocks.append(cur)
        elif cur is None:
            before.append(line)
        else:
            cur[1].append(line)
    return before, blocks


def _trim(lines):
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def build_plan(text: str, cfg: Config) -> Plan:
    lines = text.splitlines()
    pre, sections = _split_by_level(lines, 2)
    title = "Index"
    intro, general = [], []
    for line in pre:
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == 1 and title == "Index":
            title = m.group(2)
            continue
        (general if "[[" in line else intro).append(line)
    plan = Plan(title=title, intro=_trim(intro))
    if _trim(general):
        plan.pieces.append(Piece("General", _trim(general)))
    for heading, body in sections:
        if _is_history(heading, cfg.history_patterns):
            plan.pieces.append(Piece(heading, ["## " + heading, ""] + _trim(body), history=True))
            continue
        n_entries = sum(1 for l in body if CATALOG_RE.match(l))
        lead, subs = _split_by_level(body, 3)
        if n_entries > cfg.split_threshold and subs:
            if _trim(lead):
                plan.pieces.append(Piece(heading, _trim(lead)))
            for sh, sb in subs:
                if _is_history(sh, cfg.history_patterns):
                    plan.pieces.append(Piece(f"{heading} / {sh}", ["### " + sh, ""] + _trim(sb), history=True))
                else:
                    plan.pieces.append(Piece(f"{heading} / {sh}", _trim(sb)))
        else:
            plan.pieces.append(Piece(heading, _trim(body)))
    used = {"_history"}
    for p in plan.pieces:
        if p.history:
            continue
        base = slugify(p.name.replace(" / ", "--"))
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        p.slug = slug
    return plan


def render_subindex(piece: Piece) -> str:
    return f"# {piece.name}\n\n" + "\n".join(piece.lines) + "\n"


def render_history(history: list) -> str:
    out = ["# Index history", "",
           "Changelog-style blocks moved out of the master index. Not read during normal queries.", ""]
    for p in history:
        out += p.lines + [""]
    return "\n".join(out).rstrip() + "\n"


def check_links_preserved(original: str, outputs: list) -> None:
    """Abort if any [[link]] of the original is missing from the outputs."""
    missing = link_targets(original) - set().union(*[link_targets(t) for t in outputs]) if outputs \
        else link_targets(original)
    if missing:
        raise LinkLost("links lost, aborting without writing: " + ", ".join(sorted(missing)))
    n_orig = sum(1 for l in original.splitlines() if CATALOG_RE.match(l))
    n_out = sum(1 for t in outputs for l in t.splitlines() if CATALOG_RE.match(l))
    if n_orig != n_out:
        raise LinkLost(f"catalog line count changed ({n_orig} -> {n_out}), aborting without writing")


def render_master(plan: Plan, cfg: Config, master_path: Path, pages, names) -> str:
    unique_entries = set()
    rows = []
    index_dir = cfg.path(cfg.index_dir)
    for p in plan.pieces:
        if p.history:
            continue
        ents = p.entries
        unique_entries |= {norm_target(e) for e in ents}
        if pages is None:
            on_disk = "n/a"
        else:
            on_disk = str(sum(1 for e in ents if e.casefold() in names or norm_target(e) in names))
        rel = os.path.relpath(index_dir / f"{p.slug}.md", master_path.parent).replace("\\", "/")
        rows.append(f"| {p.name} | {len(ents)} | {on_disk} | [{p.slug}.md]({rel}) |")
    count = len(pages) if pages is not None else len(unique_entries)
    out = [f"# {plan.title}", ""]
    if plan.intro:
        out += plan.intro + [""]
    out += [f"<!-- KB-COUNT: {count} -->", "",
            "| Path | Entries in index | Files on disk | Sub-index |",
            "|------|-----------------:|--------------:|-----------|"] + rows
    if any(p.history for p in plan.pieces):
        hist = os.path.relpath(cfg.path(cfg.history_file), master_path.parent).replace("\\", "/")
        out += ["", f"History: [{Path(cfg.history_file).name}]({hist}) (not read during queries)."]
    return "\n".join(out) + "\n"


def cmd_split_index(cfg: Config, index_file: str, dry_run: bool = False, force: bool = False) -> int:
    src = Path(index_file)
    src = src if src.is_absolute() else cfg.root / src
    if not src.is_file():
        print(f"error: {index_file} not found")
        return 2
    original = read_text(src)
    plan = build_plan(original, cfg)
    pages = collect_pages(cfg) if cfg.path(cfg.wiki_dir).is_dir() else None
    names = resolvable_names(cfg, pages) if pages is not None else set()

    subs = [p for p in plan.pieces if not p.history]
    hist = [p for p in plan.pieces if p.history]
    sub_texts = {p.slug: render_subindex(p) for p in subs}
    hist_text = render_history(hist) if hist else None
    outputs = list(sub_texts.values()) + ([hist_text] if hist_text else [])
    try:
        check_links_preserved(original, outputs)
    except SplitError as exc:
        print(f"error: {exc}")
        return 2

    master_text = render_master(plan, cfg, src, pages, names)
    index_dir = cfg.path(cfg.index_dir)
    targets = [index_dir / f"{s}.md" for s in sub_texts] + ([cfg.path(cfg.history_file)] if hist_text else [])

    print(f"Plan: {len(subs)} sub-indices, {len(hist)} history block(s) -> {cfg.history_file if hist else '-'}")
    for p in subs:
        print(f"  {p.slug}.md  ({len(p.entries)} entries)  <- {p.name}")
    for p in hist:
        print(f"  history: {p.name}")
    print(f"  master: {len(master_text)} bytes (original: {len(original.encode('utf-8'))} bytes)")
    if dry_run:
        print("Dry run: nothing written.")
        return 0
    clash = [t for t in targets if t.exists()]
    if clash and not force:
        print("error: already exist (use --force): " + ", ".join(t.name for t in clash))
        return 2

    backup_dir = cfg.path(cfg.index_backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{src.stem}-{time.strftime('%Y%m%d-%H%M%S')}{src.suffix}"
    shutil.copy2(src, backup)
    index_dir.mkdir(parents=True, exist_ok=True)
    for slug, text in sub_texts.items():
        (index_dir / f"{slug}.md").write_text(text, encoding="utf-8", newline="\n")
    if hist_text:
        hp = cfg.path(cfg.history_file)
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text(hist_text, encoding="utf-8", newline="\n")
    src.write_text(master_text, encoding="utf-8", newline="\n")
    print(f"Done. Backup: {backup.relative_to(cfg.root).as_posix() if backup.is_relative_to(cfg.root) else backup}")
    return 0
