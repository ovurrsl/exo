# A5 — `fix/model-id-traversal`

Compare: https://github.com/exo-explore/exo/compare/main...ovurrsl:exo:fix/model-id-traversal?expand=1

## Title

```
fix(models): reject model ids that escape the models directory
```

## Description

```markdown
## Motivation

`ModelId.normalize()` turns a model id into a directory name by replacing `/`
with `--`, and callers join that onto a models directory. A single-dot or
double-dot path segment survives that transformation, so an id like `../../etc`
does not normalize into a safe name.

That matters most in `delete_model()`, which calls `shutil.rmtree` on the joined
path. The API accepts a model id from an unauthenticated LAN caller, so the
value is attacker-controlled.

## Changes

- `src/exo/shared/types/common.py`: `ModelId.__new__` rejects any id with an
  empty, `.` or `..` path segment, or containing a backslash or a NUL byte.
  Validating in the type means every construction path is covered, including
  pydantic parsing of request bodies, rather than one call site.
- `src/exo/download/download_utils.py`: `delete_model()` checks that the
  resolved target is inside the resolved models directory before `rmtree`, and
  raises otherwise. Defence in depth for the one destructive path — the type
  check should already make this unreachable.
- `src/exo/shared/tests/test_model_id.py`: new, covering both.

## Why It Works

`ModelId` subclasses `Id`, which subclasses `str`, so `__new__` is the single
point every instance passes through. Rejecting there makes an invalid id
unrepresentable rather than merely unused, and a pydantic-parsed request body
raises `ValidationError` instead of reaching the filesystem.

The `is_relative_to` check resolves both sides first, so it also catches escapes
via a symlink inside the models directory, which a purely lexical check would
miss.

## Test Plan

### Manual Testing
- Hardware: Ubuntu x86_64, Python 3.13 (no Apple Silicon available)
- Confirmed that on `main` a `ModelId` containing `..` is constructed without
  complaint, and that with this change it raises.

### Automated Testing
New file `src/exo/shared/tests/test_model_id.py`:

- Accepts ordinary Hugging Face ids (`mlx-community/Qwen3-4B-4bit`) so the
  change is not over-broad.
- Rejects `..`, `.`, `org/..`, `org//model`, `/absolute`, `trailing/`, a
  backslash, and an embedded NUL.
- Asserts that a request body carrying a bad id fails with a pydantic
  `ValidationError` rather than reaching any filesystem code.

These run on Linux with no MLX and no network.
```
