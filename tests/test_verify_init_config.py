import json
import unittest
from pathlib import Path

import helpers
from helpers import DEMO_AFTER, REPO, WikiCase, page

from wikikit import config
from wikikit.util import parse_frontmatter


def master(n):
    return f"# Index\n\n<!-- KB-COUNT: {n} -->\n"


class VerifyTests(WikiCase):
    def good(self):
        self.write("wiki/Alpha.md", page("Alpha", links="[[Beta]]"))
        self.write("wiki/Beta.md", page("Beta", extra_fm="aliases: [Bee]\n"))
        self.write("_meta/INDEX.md", master(2))
        self.write("_meta/index/all.md", "# All\n\n- [[Alpha]] — a\n- [[Beta]] — b\n")

    def codes(self):
        code, out = self.cli("verify", "--json")
        return {i["code"] for i in json.loads(out)["issues"]}

    def test_clean(self):
        self.good()
        code, out = self.cli("verify", "--fail-on-broken")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.codes(), set())

    def test_no_frontmatter(self):
        self.good()
        self.write("wiki/Gamma.md", "# Gamma\n\nnothing\n")
        self.assertIn("no-frontmatter", self.codes())

    def test_broken_link_and_alias_ignored(self):
        self.good()
        self.write("wiki/Alpha.md", page("Alpha", links="[[Bee]] [[Missing Page]] `[[in code]]`"))
        issues = json.loads(self.cli("verify", "--json")[1])["issues"]
        broken = [i["message"] for i in issues if i["code"] == "broken-link"]
        self.assertEqual(len(broken), 1)
        self.assertIn("Missing Page", broken[0])

    def test_kb_count_mismatch_and_missing(self):
        self.good()
        self.write("_meta/INDEX.md", master(5))
        self.assertIn("kb-count-mismatch", self.codes())
        self.write("_meta/INDEX.md", "# Index\n")
        self.assertIn("kb-count-missing", self.codes())

    def test_not_indexed_and_entry_without_file(self):
        self.good()
        self.write("_meta/index/all.md", "# All\n\n- [[Alpha]] — a\n- [[Ghost]] — g\n")
        self.assertEqual(self.codes() & {"not-indexed", "entry-without-file"}, {"not-indexed", "entry-without-file"})

    def test_improvable(self):
        self.good()
        self.write("wiki/Delta.md", "---\ntitle: Other\n---\n\n# Different\n")
        self.write("_meta/INDEX.md", master(3))
        self.write("_meta/index/all.md", "# All\n\n- [[Alpha]] — a\n- [[Beta]] — b\n- [[Delta]] — d\n")
        code, out = self.cli("verify", "--fail-on-broken")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.codes(), {"filename-h1", "title-h1"})

    def test_infra_files_not_pages(self):
        self.good()
        self.write("wiki/CLAUDE.md", "no frontmatter at all")
        self.write("wiki/AGENTS.md", "none")
        self.assertEqual(self.codes(), set())

    def test_fail_on_broken_exit_code(self):
        self.good()
        self.write("wiki/Gamma.md", "# Gamma\n")
        self.assertEqual(self.cli("verify")[0], 0)
        self.assertEqual(self.cli("verify", "--fail-on-broken")[0], 1)

    def test_demo_after_is_clean(self):
        code, out = helpers.run("verify", "--fail-on-broken", root=DEMO_AFTER)
        self.assertEqual(code, 0, out)


class InitTests(WikiCase):
    def test_init_creates_structure_and_verifies(self):
        target = self.tmp / "fresh"
        code, out = helpers.run("init", str(target))
        self.assertEqual(code, 0, out)
        for rel in ("wiki", "raw", "_meta/index", "_meta/_raw_pending", "wikikit.toml", "AGENTS.md",
                    "CLAUDE.md", "_meta/INDEX.md", "_meta/LOG.md", "_meta/claude-settings.example.json"):
            self.assertTrue((target / rel).exists(), rel)
        self.assertIn("KB-COUNT: 0", (target / "_meta" / "INDEX.md").read_text(encoding="utf-8"))
        cfg = config.load_config(target)  # generated toml parses and equals defaults
        self.assertEqual(cfg.split_threshold, 150)
        self.assertEqual(cfg.history_file, "_meta/index/_HISTORY.md")
        self.assertEqual(helpers.run("verify", "--fail-on-broken", root=target)[0], 0)

    def test_init_never_overwrites(self):
        target = self.tmp / "fresh2"
        target.mkdir()
        (target / "AGENTS.md").write_text("mine", encoding="utf-8")
        helpers.run("init", str(target))
        self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), "mine")


class ConfigTests(WikiCase):
    def test_defaults_without_file(self):
        cfg = config.load_config(self.tmp)
        self.assertEqual((cfg.wiki_dir, cfg.raw_dir, cfg.meta_dir), ("wiki", "raw", "_meta"))
        self.assertIn("node_modules", cfg.exclude_dirs)

    def test_override(self):
        self.write("wikikit.toml", 'wiki_dir = "notes"\n[search]\nsources = ["notes"]\n'
                   'snippet_marks = ["**", "**"]\n')
        cfg = config.load_config(self.root)
        self.assertEqual(cfg.wiki_dir, "notes")
        self.assertEqual(cfg.sources, ["notes"])
        self.assertEqual((cfg.snippet_open, cfg.snippet_close), ("**", "**"))

    def test_mini_toml_matches_tomllib_on_init_template(self):
        from wikikit.init import TOML
        data = config.mini_toml_loads(TOML)
        self.assertEqual(data["split"]["threshold"], 150)
        self.assertEqual(data["search"]["sources"], ["wiki", "raw"])
        self.assertEqual(data["search"]["snippet_marks"], ["«", "»"])
        if config._tomllib:
            self.assertEqual(data, config._tomllib.loads(TOML))

    def test_frontmatter_parser(self):
        meta, n = parse_frontmatter("---\ntitle: X\naliases:\n  - a\n  - b\ntags: [t1, t2]\n---\nbody")
        self.assertEqual(meta, {"title": "X", "aliases": ["a", "b"], "tags": ["t1", "t2"]})
        self.assertEqual(n, 7)
        self.assertEqual(parse_frontmatter("# no fm"), (None, 0))


class TemplatesSyncTests(unittest.TestCase):
    def test_root_templates_match_packaged(self):
        pkg = REPO / "src" / "wikikit" / "templates"
        for f in pkg.iterdir():
            self.assertEqual(f.read_bytes(), (REPO / "templates" / f.name).read_bytes(), f.name)

    def test_settings_example_is_valid_json(self):
        d = json.loads((REPO / "templates" / "claude-settings.example.json").read_text(encoding="utf-8"))
        self.assertIn("Edit(raw/**)", d["permissions"]["deny"])
        self.assertIn("Edit(_meta/LOG.md)", d["permissions"]["deny"])


if __name__ == "__main__":
    unittest.main()
