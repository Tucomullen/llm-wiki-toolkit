"""Configuration loading (wikikit.toml) with sensible defaults."""
from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:  # Python 3.11+
    import tomllib as _tomllib
except ImportError:  # pragma: no cover - Python 3.10 fallback
    _tomllib = None

CONFIG_NAME = "wikikit.toml"

DEFAULT_EXCLUDES = ["node_modules", ".git", ".venv", "__pycache__", "dist", "build", "tmp"]
DEFAULT_HISTORY_PATTERNS = [
    r"\bhistory\b",
    r"\bchangelog\b",
    r"\bchange log\b",
    r"\bupdate log\b",
    r"\brecent (updates|changes)\b",
]


class ConfigError(Exception):
    pass


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).strip()


def _parse_value(raw: str):
    raw = raw.strip()
    if raw.startswith("["):
        inner = raw[1:-1]
        items = re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'|([^,\s][^,]*)', inner)
        vals = []
        for a, b, c in items:
            if a or (not b and not c):
                vals.append(a.encode().decode("unicode_escape") if "\\" in a else a)
            elif b:
                vals.append(b)
            else:
                vals.append(_parse_value(c))
        return vals
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        s = raw[1:-1]
        return s.replace('\\"', '"').replace("\\\\", "\\") if "\\" in s else s
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"unsupported TOML value: {raw!r}")


def mini_toml_loads(text: str) -> dict:
    """Tiny TOML subset parser (tables, strings, ints, bools, string arrays).

    Only used on Python 3.10, where ``tomllib`` is not available.
    """
    data: dict = {}
    cur = data
    pending = ""
    for line in text.splitlines():
        line = _strip_comment(line)
        if not line and not pending:
            continue
        if pending:
            pending += " " + line
            if pending.count("[") <= pending.count("]"):
                k, v = pending.split("=", 1)
                cur[k.strip()] = _parse_value(v)
                pending = ""
            continue
        m = re.match(r"^\[([A-Za-z0-9_.-]+)\]$", line)
        if m:
            cur = data
            for part in m.group(1).split("."):
                cur = cur.setdefault(part, {})
            continue
        if "=" not in line:
            raise ConfigError(f"cannot parse line: {line!r}")
        k, v = line.split("=", 1)
        if v.strip().startswith("[") and v.count("[") > v.count("]"):
            pending = line
            continue
        cur[k.strip()] = _parse_value(v)
    return data


def loads_toml(text: str) -> dict:
    if _tomllib is not None:
        try:
            return _tomllib.loads(text)
        except _tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"invalid {CONFIG_NAME}: {exc}")
    return mini_toml_loads(text)


@dataclass
class Config:
    root: Path
    wiki_dir: str = "wiki"
    raw_dir: str = "raw"
    meta_dir: str = "_meta"
    index_dir: str = "_meta/index"
    master_index: str = "_meta/INDEX.md"
    history_file: str = "_meta/index/_HISTORY.md"
    log_file: str = "_meta/LOG.md"
    log_archive_dir: str = "_meta/_archive/log_applied"
    raw_pending_dir: str = "_meta/_raw_pending"
    index_backup_dir: str = "_meta/_archive/index_backups"
    infra_files: list = field(default_factory=lambda: ["CLAUDE.md", "AGENTS.md"])
    sources: list = field(default_factory=lambda: ["wiki", "raw"])
    exclude_dirs: list = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    db_path: str = ""
    snippet_open: str = "«"
    snippet_close: str = "»"
    chunk_min: int = 1200
    chunk_max: int = 1800
    split_threshold: int = 150
    history_patterns: list = field(default_factory=lambda: list(DEFAULT_HISTORY_PATTERNS))

    def path(self, rel: str) -> Path:
        return self.root / rel

    def resolved_db_path(self) -> Path:
        if self.db_path:
            p = Path(self.db_path)
            return p if p.is_absolute() else self.root / p
        digest = hashlib.sha1(str(self.root.resolve()).encode("utf-8")).hexdigest()[:12]
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        else:
            base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        return base / "wikikit" / f"{digest}.sqlite"


def find_root(start: Path) -> Path:
    """Walk up from ``start`` looking for wikikit.toml; fall back to ``start``."""
    start = start.resolve()
    for d in [start, *start.parents]:
        if (d / CONFIG_NAME).is_file():
            return d
    return start


def load_config(root: Path) -> Config:
    cfg = Config(root=Path(root))
    f = cfg.root / CONFIG_NAME
    if not f.is_file():
        return cfg
    data = loads_toml(f.read_text(encoding="utf-8"))
    for key in ("wiki_dir", "raw_dir", "meta_dir", "index_dir", "master_index", "history_file",
                "log_file", "log_archive_dir", "raw_pending_dir", "index_backup_dir"):
        if key in data:
            setattr(cfg, key, str(data[key]))
    s = data.get("search", {})
    if "sources" in s:
        cfg.sources = [str(x) for x in s["sources"]]
    if "exclude_dirs" in s:
        cfg.exclude_dirs = [str(x) for x in s["exclude_dirs"]]
    if "db_path" in s:
        cfg.db_path = str(s["db_path"])
    if "snippet_marks" in s and len(s["snippet_marks"]) == 2:
        cfg.snippet_open, cfg.snippet_close = s["snippet_marks"]
    if "chunk_min" in s:
        cfg.chunk_min = int(s["chunk_min"])
    if "chunk_max" in s:
        cfg.chunk_max = int(s["chunk_max"])
    sp = data.get("split", {})
    if "threshold" in sp:
        cfg.split_threshold = int(sp["threshold"])
    if "history_patterns" in sp:
        cfg.history_patterns = [str(x) for x in sp["history_patterns"]]
    v = data.get("verify", {})
    if "infra_files" in v:
        cfg.infra_files = [str(x) for x in v["infra_files"]]
    return cfg
