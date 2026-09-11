# A1 — `docs/zenoh-namespace-env`

Compare: https://github.com/exo-explore/exo/compare/main...ovurrsl:exo:docs/zenoh-namespace-env?expand=1

## Title

```
docs: EXO_LIBP2P_NAMESPACE was renamed to EXO_ZENOH_NAMESPACE
```

## Description

```markdown
## Motivation

The README documents `EXO_LIBP2P_NAMESPACE` in four places, including a runnable
example (`EXO_LIBP2P_NAMESPACE=my-dev-cluster uv run exo`). Since the zenoh
migration (#2132), `src/exo/main.py` refuses to start when that variable is set:

    ValueError: EXO_LIBP2P_NAMESPACE has been removed - use EXO_ZENOH_NAMESPACE instead

So the command the documentation tells a new contributor to run is exactly the
one that cannot work.

## Changes

Renames `EXO_LIBP2P_NAMESPACE` to `EXO_ZENOH_NAMESPACE` in the four places the
README mentions it (lines 249, 256, 322 and 342). Documentation only; no code
is touched.

## Why It Works

`src/exo/main.py:343-345` reads `EXO_ZENOH_NAMESPACE` and raises on the old
name. After this change the documented variable is the one the code actually
reads, so the example command starts a node instead of aborting.

## Test Plan

### Manual Testing
- Hardware: Ubuntu x86_64, Python 3.13 (no Apple Silicon available)
- Ran the README command with the old variable name and reproduced the
  `ValueError` above; re-ran it with `EXO_ZENOH_NAMESPACE` and the node started.

### Automated Testing
No automated tests apply. The change is limited to README prose, and
`grep -r EXO_LIBP2P_NAMESPACE` returns nothing after it.
```
