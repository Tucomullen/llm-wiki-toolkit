"""`wikikit log append`: append-only writes to the log with integrity checks."""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from .config import Config
from .util import read_text, sha256_bytes

HEADER_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] ([A-Z][A-Z0-9_-]*) \| (.+?)\s*$", re.M)


def cmd_log_append(cfg: Config, entry_file: str) -> int:
    entry = Path(entry_file)
    entry = entry if entry.is_absolute() else Path.cwd() / entry
    if not entry.is_file():
        print(f"error: {entry_file} not found")
        return 2
    log = cfg.path(cfg.log_file)
    if not log.is_file():
        print(f"error: log {cfg.log_file} not found (run `wikikit init`)")
        return 2
    text = read_text(entry).replace("\r\n", "\n")
    first = next((l for l in text.split("\n") if l.strip()), "")
    if not HEADER_RE.match(first):
        print("error: entry must start with a header like '## [YYYY-MM-DD] TYPE | title'")
        return 2
    headers = [m.group(0).strip() for m in HEADER_RE.finditer(text)]
    old = log.read_bytes()
    existing = {m.group(0).strip() for m in HEADER_RE.finditer(old.decode("utf-8", errors="replace"))}
    dup = [h for h in headers if h in existing]
    if dup:
        print(f"error: header already exists in the log: {dup[0]}")
        return 2

    add = b""
    if old and not old.endswith(b"\n"):
        add += b"\n"
    if old:
        add += b"\n"
    add += text.strip("\n").encode("utf-8") + b"\n"
    old_hash, old_size = sha256_bytes(old), len(old)
    with open(log, "ab") as fh:
        fh.write(add)
        fh.flush()
        os.fsync(fh.fileno())
    new = log.read_bytes()
    if sha256_bytes(new[:old_size]) != old_hash or len(new) != old_size + len(add):
        print("FATAL: integrity check failed after append; inspect the log and restore it from backup. "
              "The entry file was NOT moved.")
        return 3
    arch = cfg.path(cfg.log_archive_dir)
    arch.mkdir(parents=True, exist_ok=True)
    dest = arch / entry.name
    if dest.exists():
        dest = arch / f"{entry.stem}-{time.strftime('%Y%m%d-%H%M%S')}{entry.suffix}"
    shutil.move(str(entry), str(dest))
    print(f"Appended {len(add)} bytes ({len(headers)} entry/entries); previous content verified unchanged "
          f"(sha256 {old_hash[:12]}...). Entry archived to {dest.name}.")
    return 0
