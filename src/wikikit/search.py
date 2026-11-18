"""`wikikit search`: local SQLite FTS5 index and queries."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from .config import Config
from .extract import SUPPORTED, MissingExtra, chunk_unit, extract
from .util import is_cloud_only

SCHEMA_VERSION = 1


class SearchError(Exception):
    pass


def _connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    try:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _probe USING fts5(x)")
        con.execute("DROP TABLE IF EXISTS _probe")
    except sqlite3.OperationalError as exc:
        raise SearchError(f"this Python's SQLite lacks FTS5: {exc}")
    return con


def _init_schema(con, full: bool):
    ver = con.execute("PRAGMA user_version").fetchone()[0]
    if full or ver != SCHEMA_VERSION:
        for t in ("fts", "files", "chunk_map", "skipped"):
            con.execute(f"DROP TABLE IF EXISTS {t}")
    con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
        title, heading, body, path UNINDEXED, source UNINDEXED, project UNINDEXED, loc UNINDEXED,
        tokenize='unicode61 remove_diacritics 2', prefix='3')""")
    con.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, source TEXT, project TEXT, "
                "mtime_ns INTEGER, size INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS chunk_map(rid INTEGER PRIMARY KEY, path TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS chunk_map_path ON chunk_map(path)")
    con.execute("CREATE TABLE IF NOT EXISTS skipped(path TEXT PRIMARY KEY, reason TEXT)")
    con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def _walk(cfg: Config):
    for source in cfg.sources:
        base = cfg.path(source)
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in cfg.exclude_dirs)
            for fn in sorted(filenames):
                if Path(fn).suffix.lower() in SUPPORTED:
                    p = Path(dirpath) / fn
                    parts = p.relative_to(base).parts
                    yield source, (parts[0] if len(parts) > 1 else ""), p


def _delete_file(con, path: str):
    for (rid,) in con.execute("SELECT rid FROM chunk_map WHERE path=?", (path,)).fetchall():
        con.execute("DELETE FROM fts WHERE rowid=?", (rid,))
    con.execute("DELETE FROM chunk_map WHERE path=?", (path,))
    con.execute("DELETE FROM files WHERE path=?", (path,))


def build_index(cfg: Config, full: bool = False) -> dict:
    con = _connect(cfg.resolved_db_path())
    try:
        _init_schema(con, full)
        known = {r[0]: (r[1], r[2]) for r in con.execute("SELECT path, mtime_ns, size FROM files")}
        con.execute("DELETE FROM skipped")
        seen, stats = set(), {"added": 0, "updated": 0, "unchanged": 0, "removed": 0, "skipped": 0, "chunks": 0}
        for source, project, p in _walk(cfg):
            rel = p.relative_to(cfg.root).as_posix()
            seen.add(rel)
            try:
                st = p.stat()
            except OSError as exc:
                con.execute("INSERT OR REPLACE INTO skipped VALUES(?,?)", (rel, f"stat failed: {exc}"))
                stats["skipped"] += 1
                continue
            if is_cloud_only(st):
                if rel in known:
                    _delete_file(con, rel)
                con.execute("INSERT OR REPLACE INTO skipped VALUES(?,?)", (rel, "cloud-only placeholder (not downloaded)"))
                stats["skipped"] += 1
                continue
            if known.get(rel) == (st.st_mtime_ns, st.st_size):
                stats["unchanged"] += 1
                continue
            try:
                ex = extract(p)
            except MissingExtra as exc:
                con.execute("INSERT OR REPLACE INTO skipped VALUES(?,?)", (rel, str(exc)))
                stats["skipped"] += 1
                continue
            except Exception as exc:  # corrupt file, bad encoding, ...
                con.execute("INSERT OR REPLACE INTO skipped VALUES(?,?)", (rel, f"extract failed: {exc}"))
                stats["skipped"] += 1
                continue
            existed = rel in known
            if existed:
                _delete_file(con, rel)
            n = 0
            for unit in ex.units:
                for ch in chunk_unit(unit, cfg.chunk_min, cfg.chunk_max):
                    cur = con.execute("INSERT INTO fts(title, heading, body, path, source, project, loc) "
                                      "VALUES(?,?,?,?,?,?,?)",
                                      (ex.title, ch.heading, ch.body, rel, source, project, ch.loc))
                    con.execute("INSERT INTO chunk_map VALUES(?,?)", (cur.lastrowid, rel))
                    n += 1
            con.execute("INSERT OR REPLACE INTO files VALUES(?,?,?,?,?)",
                        (rel, source, project, st.st_mtime_ns, st.st_size))
            stats["updated" if existed else "added"] += 1
            stats["chunks"] += n
        for rel in set(known) - seen:
            _delete_file(con, rel)
            stats["removed"] += 1
        con.commit()
        return stats
    finally:
        con.close()


def build_match(text: str, any_: bool) -> str:
    terms = [a or b for a, b in re.findall(r'"([^"]+)"|(\S+)', text)]
    if not terms:
        raise SearchError("empty query")
    quoted = ['"' + t.replace('"', '""') + '"' for t in terms]
    return (" OR " if any_ else " AND ").join(quoted)


def run_query(cfg: Config, text: str, limit=10, source=None, project=None, any_=False, raw_fts=False,
              per_file=2) -> list:
    db = cfg.resolved_db_path()
    if not db.is_file():
        raise SearchError("no index found; run `wikikit search index` first")
    match = text if raw_fts else build_match(text, any_)
    sql = ("SELECT path, source, project, loc, heading, title, bm25(fts, 1.0, 2.0, 1.0, 0, 0, 0, 0), "
           "snippet(fts, 2, ?, ?, '…', 24) FROM fts WHERE fts MATCH ?")
    args = [cfg.snippet_open, cfg.snippet_close, match]
    if source:
        sql += " AND lower(source)=lower(?)"
        args.append(source)
    if project:
        sql += " AND lower(project)=lower(?)"
        args.append(project)
    sql += " ORDER BY 7 LIMIT ?"
    args.append(max(limit * max(per_file, 1) * 10, 200))
    con = sqlite3.connect(str(db))
    try:
        try:
            rows = con.execute(sql, args).fetchall()
        except sqlite3.OperationalError as exc:
            if raw_fts:
                raise SearchError(f"invalid FTS5 query {text!r}: {exc}. "
                                  "See https://sqlite.org/fts5.html#full_text_query_syntax")
            raise SearchError(f"query failed: {exc}")
    finally:
        con.close()
    out, per = [], {}
    for path, src, proj, loc, heading, title, score, snip in rows:
        if per.get(path, 0) >= per_file:
            continue
        per[path] = per.get(path, 0) + 1
        out.append({"path": path, "source": src, "project": proj, "loc": loc, "title": title,
                    "heading": heading, "score": round(-score, 4), "snippet": " ".join(snip.split())})
        if len(out) >= limit:
            break
    return out


def get_stats(cfg: Config) -> dict:
    db = cfg.resolved_db_path()
    if not db.is_file():
        raise SearchError("no index found; run `wikikit search index` first")
    con = sqlite3.connect(str(db))
    try:
        by_source = dict(con.execute("SELECT source, COUNT(*) FROM files GROUP BY source").fetchall())
        chunks = con.execute("SELECT COUNT(*) FROM chunk_map").fetchone()[0]
        skipped = con.execute("SELECT path, reason FROM skipped ORDER BY path").fetchall()
    finally:
        con.close()
    return {"db": str(db), "db_bytes": db.stat().st_size, "files_by_source": by_source,
            "files": sum(by_source.values()), "chunks": chunks,
            "skipped": [{"path": p, "reason": r} for p, r in skipped]}


def cmd_search(cfg: Config, args) -> int:
    try:
        if args.search_cmd == "index":
            s = build_index(cfg, full=args.full)
            print(f"Index updated at {cfg.resolved_db_path()}")
            print(f"  added {s['added']}, updated {s['updated']}, unchanged {s['unchanged']}, "
                  f"removed {s['removed']}, skipped {s['skipped']}, new chunks {s['chunks']}")
            if s["skipped"]:
                print("  (see `wikikit search stats` for skipped files and reasons)")
        elif args.search_cmd == "stats":
            s = get_stats(cfg)
            print(f"DB: {s['db']} ({s['db_bytes']} bytes)")
            print(f"Files: {s['files']}  Chunks: {s['chunks']}")
            for k, v in sorted(s["files_by_source"].items()):
                print(f"  {k}: {v}")
            print(f"Skipped: {len(s['skipped'])}")
            for item in s["skipped"]:
                print(f"  {item['path']}: {item['reason']}")
        else:
            res = run_query(cfg, args.text, args.n, args.source, args.project, args.any, args.fts, args.per_file)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            elif not res:
                print("No results.")
            else:
                for i, r in enumerate(res, 1):
                    head = f" > {r['heading']}" if r["heading"] else ""
                    print(f"{i}. {r['path']} [{r['loc']}]  {r['title']}{head}  (score {r['score']})")
                    print(f"   {r['snippet']}")
    except SearchError as exc:
        print(f"error: {exc}")
        return 2
    return 0
