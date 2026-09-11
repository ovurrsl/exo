# A7 — `docs/test-setup-workspace`

Compare: https://github.com/exo-explore/exo/compare/main...ovurrsl:exo:docs/test-setup-workspace?expand=1

## Title

```
docs: running the tests needs the workspace packages installed
```

## Description

```markdown
## Motivation

`uv run pytest` as documented in `AGENTS.md` and `CONTRIBUTING.md` fails at
collection on a fresh clone:

    ModuleNotFoundError: No module named 'exo_tools'

`tests/conftest.py` imports `exo_tools`, which lives in the `tools` workspace
member. A plain `uv sync` installs the project but not the workspace members, so
the documented command cannot work until `--all-packages` is passed. Nothing in
the documentation says so, and CI does not catch it because the macOS runner
installs differently.

## Changes

Documentation only.

- `CONTRIBUTING.md`: a short paragraph in the Testing section giving the two
  commands to run, and naming the exact error you get without them.
- `AGENTS.md`: the same `uv sync --all-packages` line in the command block,
  immediately above `uv run pytest`.

## Why It Works

`tools` is declared under `[tool.uv.workspace] members`. `uv sync
--all-packages` installs every workspace member, which puts `exo_tools` on the
path before `tests/conftest.py` imports it. With that, collection proceeds
normally.

## Test Plan

### Manual Testing
- Hardware: Ubuntu x86_64, Python 3.13 (no Apple Silicon available)
- Ran `uv run pytest` after a plain `uv sync` and reproduced the
  `ModuleNotFoundError` above.
- Re-ran after `uv sync --all-packages --extra mlx-cpu` and collection
  succeeded.

### Automated Testing
No automated tests apply; the change is limited to documentation prose.
```
