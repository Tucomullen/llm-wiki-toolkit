"""Command-line interface."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, find_root, load_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wikikit", description="Tools for Markdown wikis maintained by AI agents.")
    p.add_argument("--root", help="wiki root (default: nearest parent with wikikit.toml, else cwd)")
    p.add_argument("--version", action="version", version=f"wikikit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("split-index", help="split a monolithic index into master + sub-indices")
    s.add_argument("index_file")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--force", action="store_true", help="overwrite existing sub-index files")

    se = sub.add_parser("search", help="full-text search")
    ss = se.add_subparsers(dest="search_cmd", required=True)
    i = ss.add_parser("index", help="build/update the index")
    i.add_argument("--full", action="store_true", help="rebuild from scratch")
    q = ss.add_parser("query", help="run a query")
    q.add_argument("text")
    q.add_argument("-n", type=int, default=10)
    q.add_argument("--source")
    q.add_argument("--project")
    q.add_argument("--any", action="store_true", help="OR instead of AND")
    q.add_argument("--fts", action="store_true", help="raw FTS5 syntax")
    q.add_argument("--per-file", type=int, default=2)
    q.add_argument("--json", action="store_true")
    ss.add_parser("stats", help="index statistics")

    lg = sub.add_parser("log", help="append-only log")
    ls = lg.add_subparsers(dest="log_cmd", required=True)
    la = ls.add_parser("append")
    la.add_argument("entry")

    rw = sub.add_parser("raw", help="create-only raw/ writes")
    rs = rw.add_subparsers(dest="raw_cmd", required=True)
    rsave = rs.add_parser("save")
    rsave.add_argument("file")
    rsave.add_argument("--name")

    v = sub.add_parser("verify", help="check wiki integrity")
    v.add_argument("--fail-on-broken", action="store_true")
    v.add_argument("--json", action="store_true")

    ini = sub.add_parser("init", help="create the minimal structure")
    ini.add_argument("dir", nargs="?", default=None)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "init":
            root = Path(args.dir or args.root or Path.cwd()).resolve()
        else:
            root = Path(args.root).resolve() if args.root else find_root(Path.cwd())
        cfg = load_config(root)
    except ConfigError as exc:
        print(f"error: {exc}")
        return 2

    if args.cmd == "init":
        from .init import cmd_init
        return cmd_init(cfg)
    if args.cmd == "split-index":
        from .splitindex import cmd_split_index
        return cmd_split_index(cfg, args.index_file, args.dry_run, args.force)
    if args.cmd == "search":
        from .search import cmd_search
        return cmd_search(cfg, args)
    if args.cmd == "log":
        from .logappend import cmd_log_append
        return cmd_log_append(cfg, args.entry)
    if args.cmd == "raw":
        from .rawsave import cmd_raw_save
        return cmd_raw_save(cfg, args.file, args.name)
    from .verify import cmd_verify
    return cmd_verify(cfg, args.fail_on_broken, args.json)


if __name__ == "__main__":
    sys.exit(main())
