"""`wikikit raw save`: create-only copy into raw/."""
from __future__ import annotations

import re
from pathlib import Path

from .config import Config
from .util import sha256_file

BAD_CHARS = re.compile(r'[\x00-\x1f<>:"|?*/\\]')


def validate_name(name: str) -> str | None:
    """Return an error message or None if the name is acceptable."""
    if not name or name.strip() != name:
        return "empty name or leading/trailing whitespace"
    if "/" in name or "\\" in name:
        return "name must not contain path separators"
    if ".." in name:
        return "name must not contain '..'"
    if BAD_CHARS.search(name):
        return "name contains forbidden characters"
    if name.startswith("."):
        return "name must not start with '.'"
    return None


def cmd_raw_save(cfg: Config, file: str, name: str | None) -> int:
    src = Path(file)
    src = (src if src.is_absolute() else Path.cwd() / src).resolve()
    pending = cfg.path(cfg.raw_pending_dir).resolve()
    if not src.is_file():
        print(f"error: {file} not found")
        return 2
    if src.parent != pending:
        print(f"error: only files directly inside {cfg.raw_pending_dir}/ can be saved")
        return 2
    final = name if name is not None else src.name
    err = validate_name(final)
    if err:
        print(f"error: invalid name {final!r}: {err}")
        return 2
    raw = cfg.path(cfg.raw_dir)
    raw.mkdir(parents=True, exist_ok=True)
    dest = raw / final
    if dest.exists():
        print(f"error: {cfg.raw_dir}/{final} already exists; raw files are never overwritten")
        return 2
    data = src.read_bytes()
    try:
        with open(dest, "xb") as fh:  # exclusive create: never overwrites
            fh.write(data)
    except FileExistsError:
        print(f"error: {cfg.raw_dir}/{final} already exists; raw files are never overwritten")
        return 2
    if sha256_file(dest) != sha256_file(src):
        dest.unlink()
        print("error: SHA-256 mismatch after copy; copy removed, original kept")
        return 3
    src.unlink()
    print(f"Saved {cfg.raw_dir}/{final} (sha256 {sha256_file(dest)[:12]}...); original removed from pending.")
    return 0
