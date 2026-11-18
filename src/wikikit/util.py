"""Shared helpers: frontmatter, wikilinks, hashing, file attributes."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

LINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
CATALOG_RE = re.compile(r"^\s*[-*]\s+\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
KBCOUNT_RE = re.compile(r"<!--\s*KB-COUNT:\s*(\d+)\s*-->")

ATTR_OFFLINE = 0x1000
ATTR_RECALL_ON_DATA_ACCESS = 0x400000


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig", errors="replace")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def is_cloud_only(st) -> bool:
    """True for Windows cloud placeholders (opening them would download the file)."""
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & (ATTR_OFFLINE | ATTR_RECALL_ON_DATA_ACCESS))


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "section"


def norm_target(t: str) -> str:
    t = t.strip().replace("\\", "/")
    t = t.rsplit("/", 1)[-1]
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.strip().casefold()


def link_targets(text: str) -> set:
    return {m.group(1).strip() for m in LINK_RE.finditer(text)}


def strip_code(text: str) -> str:
    out, fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            fence = not fence
            continue
        if not fence:
            out.append(re.sub(r"`[^`\n]*`", "", line))
    return "\n".join(out)


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def _parse_yaml_block(lines):
    meta, key, found = {}, None, False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            found = True
            key, val = m.group(1), m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                meta[key] = [_unquote(x) for x in val[1:-1].split(",") if x.strip()]
            elif val == "":
                meta[key] = []
            else:
                meta[key] = _unquote(val)
        else:
            m2 = re.match(r"^\s+-\s+(.*)$", line)
            if m2 and key is not None and isinstance(meta.get(key), list):
                meta[key].append(_unquote(m2.group(1)))
            elif m2 and key is not None and meta.get(key) == "":
                meta[key] = [_unquote(m2.group(1))]
    return meta if (found or not any(l.strip() for l in lines)) else None


def parse_frontmatter(text: str):
    """Return (meta or None, number_of_lines_consumed)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, 0
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            meta = _parse_yaml_block(lines[1:i])
            return (meta, i + 1) if meta is not None else (None, 0)
    return None, 0


def first_h1(lines) -> str | None:
    fence = False
    for line in lines:
        if FENCE_RE.match(line):
            fence = not fence
            continue
        if not fence:
            m = re.match(r"^#\s+(.*?)\s*#*\s*$", line)
            if m:
                return m.group(1).strip()
    return None
