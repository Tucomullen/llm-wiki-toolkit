# Contributing

Thanks for helping. This project values small, boring, well-tested tools.

## Setup

```bash
git clone <your fork>
cd llm-wiki-toolkit
pip install -e .[docs]        # [docs] is optional
python -m unittest discover -s tests -v
```

The tests use only the standard library. They run in temporary folders and never touch your real wiki.

## Ground rules

- **Core stays standard-library only** (Python 3.10+). Optional features go behind an extra in `pyproject.toml` and must degrade with a clear message when missing.
- **Safety invariants are sacred**: `raw save` never overwrites, `log append` only appends and verifies, `split-index` never writes if a link would be lost. Any change near them needs a test for the rejection case.
- **Cross-platform**: use `pathlib`, write files with `newline="\n"`, and never assume a path separator. CI runs Linux, macOS and Windows on Python 3.10-3.13.
- **Examples use invented data only.** Do not add real names, companies or paths anywhere in the repository.
- Code, comments and docs are in English.

## Pull requests

1. Open an issue first for anything bigger than a small fix.
2. Add or update tests. Run the whole suite.
3. Update `README.md` (and `README.es.md` if the change affects the quickstart or command table).
4. Keep PRs focused; describe what changed and how you checked it.

Look at [ROADMAP.md](ROADMAP.md) for tasks labelled **good first issue**.

By contributing you agree your work is licensed under the MIT License. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).
