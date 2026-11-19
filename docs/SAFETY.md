# Change safety policy

This repository protects historical/source material and prevents accidental deletions.

## Install local Git hooks (opt-in)

From the repository root, run:

```bash
git config --local core.hooksPath .githooks
```

This enables `pre-commit` and `pre-push` for **this clone only**. It does not
change your global Git settings or install hooks in someone else's clone.
You can inspect both hooks in `.githooks/` before enabling them. On macOS/Linux,
if your checkout does not retain executable bits, run `chmod +x .githooks/*`.

## What is checked

- Any deletion or rename/copy in a staged change or pull request is rejected.
- Existing files under a `raw/` directory or named `_meta/LOG.md` cannot be modified.
- New files can be added, including new `raw/` files.
- Local `pre-push` refuses direct pushes to `main`; use a pull request.
- GitHub Actions checks the changes proposed in a PR and runs tests on Linux,
  Windows and macOS. It additionally builds and installs a wheel, then runs a
  disposable end-to-end CLI demonstration.

## Important limitations

- Local hooks can be bypassed, and CI checks are effective only when branch
  protection **requires them to pass**. Configure branch rules for `main` in
  GitHub Settings > Rules > Rulesets after the new checks are green.
- Repo admins can still modify rules, and a PR that changes its own guard script
  or workflow must receive careful manual review. This is defense in depth,
  not tamper-proof archival storage.
- The CLI's `raw save` intentionally removes a temporary staging file *after*
  saving its content with a checksum. The Git guard governs repository changes,
  not runtime files in an end-user's wiki.
- Any legitimate deletion/rename or migration of protected content requires a
  separately reviewed change to the guard policy, with an explicit rationale.

Review the PR's **Files changed** tab and check for unexpected modifications
before merging. Do not force-push or merge automatically.


## Independent security check (iteration 5)

The required `safety` job runs `scripts/trusted_safety_policy.py` from
immutable commit `1b474c31c8aa6dff0d5d2a17fc0c8ce75a17a435`, checked out
to `_trusted_safety/`. This policy is evaluated against Git's base/head
diff and does **not** execute any script supplied by the proposed PR.
Local hooks and `scripts/safety_guard.py` remain available for early feedback,
but are not the authoritative enforcement mechanism.

The pinned policy forbids deletion, type changes, renamed/copied files,
and edits to existing `raw/` or `_meta/LOG.md` files. It permits normal
source edits and additions. The policy handles NUL-delimited Git paths,
rejects malformed inputs, and fails closed when Git cannot produce a diff.

**Security limitation:** GitHub Actions normally loads a `pull_request`
workflow from the PR's source, so an attacker who can edit that workflow
may remove the step that checks the immutable policy, or replace the job
with a no-op that retains the mandatory `safety` status name.
A pinned script in that PR workflow **does not solve workflow tampering**.
Before declaring the PR safe to merge, move the authoritative check
outside PR-controlled workflow definitions, for example into a separate
restricted policy repository with a trusted workflow that reports a
distinct required check via GitHub App, or a carefully audited
`pull_request_target` workflow on protected `main` that executes no
PR-controlled code and has only read permissions. Confirm a negative
tampering scenario fails to satisfy the required Ruleset status.
Do not use `pull_request_target` to build/test the PR with credentials.

The regression tests in `tests/test_trusted_safety_policy.py` verify
allowed additions/edits and forbidden deletion, type changes, raw/log
edits, renames/copies, and invalid Git diff records. Their presence in
the PR does not make them authoritative; the trusted execution must
explicitly run approved tests.
