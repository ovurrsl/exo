# Issue draft — `uv sync --extra mlx-cpu` produces an unimportable mlx on Linux

**This is an issue report, not a pull request.** A fix requires a decision only
the maintainers can make, for reasons given at the end.

Open at: https://github.com/exo-explore/exo/issues/new

---

## Title

```
Linux: --extra mlx-cpu installs an ABI-incompatible mlx; import mlx.core fails
```

## Body

```markdown
The README's Linux instructions are:

    uv sync --extra mlx-cpu
    uv run exo

On Linux x86_64 that produces an installation where `import mlx.core` raises,
so exo cannot start and 13 test modules fail to collect:

    ImportError: .../mlx/core.cpython-313-x86_64-linux-gnu.so: undefined symbol:
    _ZN3mlx4core6linalg3detERKNS0_5arrayESt7variantIJSt9monostateNS0_6StreamENS0_17ThreadLocalStreamENS0_6DeviceEEE

This is the path the README calls out as the primary one for Linux users
("Currently, exo runs on CPU on Linux"), so I think it is worth fixing rather
than working around.

## Root cause

`mlx-cpu` is a backend-only distribution. It ships `mlx/lib/libmlx.so` and the
Python sources, but no compiled extension module — installed alone it gives
`ModuleNotFoundError: No module named 'mlx.core'`. The extension module comes
from the `mlx` distribution, and the two must be built against the same libmlx.

`exo[mlx-cpu]` is defined as `["exo[mlx]", "mlx-cpu==0.31.2"]`, and `exo[mlx]`
pins `mlx==0.32.0`, which `[tool.uv.sources]` overrides on Linux to a wheel from
the `rltakashige/mlx-jaccl-fix-small-recv` fork. So the installed tree is:

| file | comes from |
|---|---|
| `mlx/core.cpython-313-x86_64-linux-gnu.so` | `mlx` 0.32.0, the JACCL fork wheel |
| `mlx/lib/libmlx.so` | `mlx-cpu` 0.31.2, stock PyPI |

The fork's extension module needs symbols that the stock 0.31.2 libmlx does not
export. Confirmed directly:

    $ nm -D --undefined-only mlx/core.cpython-313-x86_64-linux-gnu.so | grep 6linalg3det
                     U _ZN3mlx4core6linalg3detERKNS0_5arrayE...
    $ nm -D --defined-only mlx/lib/libmlx.so | grep -c 6linalg3det
    0

The source override was introduced by #2087 ("use custom mlx sources for
linux"), which applies the fork wheel to all of Linux, including the CPU extra.

## Combinations tested

All on Ubuntu x86_64, Python 3.13, each in a clean virtualenv:

| `mlx` | `mlx-cpu` | result |
|---|---|---|
| JACCL fork 0.32.0 | 0.31.2 — *current config* | `ImportError: undefined symbol ...linalg::det` |
| JACCL fork 0.32.0 | 0.32.0 | `ImportError: undefined symbol ...astype` |
| stock PyPI 0.32.0 | 0.31.2 | `ImportError: undefined symbol ...diff` |
| **stock PyPI 0.32.0** | **0.32.0** | **works** — CPU device, arithmetic evaluates |
| not installed | 0.32.0 | `ModuleNotFoundError: No module named 'mlx.core'` |

So two things are both true: the versions have to match each other, **and** the
CPU backend needs the stock `mlx` wheel rather than the fork's.

## What fixing it unlocks

This is the part that turned the report from "setup is awkward" into something
I think is worth your time. After installing a matching pair by hand (stock
`mlx==0.32.0` plus `mlx-cpu==0.32.0`, plus the CPU torch build the `mlx` extra
already declares), the **entire test suite passes on Linux**, using the same
command CI runs on macOS:

    $ EXO_TESTS=1 uv run pytest src -m "not slow" --import-mode=importlib -q
    467 passed, 5 skipped, 190 deselected in 63.82s

Sixty-four seconds, on a plain `ubuntu-latest`-class machine, with no GPU and
no Apple hardware. `pipeline.yml` currently runs pytest only on the macOS
runner (line 106, `if: runner.os == 'macOS'`); the Linux runners do `nix build`
and `nix flake check` but never execute a test. So a Linux job is available for
about a minute of runner time, and the only thing standing between you and it
is this packaging bug.

Once the resolution is fixed, the step is roughly:

```yaml
      - name: Run pytest (Linux)
        if: matrix.system == 'x86_64-linux'
        run: |
          uv sync --all-packages --extra mlx-cpu
          EXO_TESTS=1 uv run pytest src -m "not slow" --import-mode=importlib
```

`--all-packages` is needed because `tests/conftest.py` imports `exo_tools` from
the `tools` workspace member; that is a separate documentation fix I have open
as #2304.

I am not proposing that step here, because today it would go red for exactly
the reason this issue describes. Happy to open it as a follow-up once the
resolution is sorted.

## One caveat about what a Linux job can and cannot cover

Worth knowing before you weigh this: exo's peer discovery joins an IPv6
multicast group (`rust/networking/src/discovery.rs`) and zenoh listens on
`tcp/[::]`, so a node cannot start at all on a host without IPv6. GitHub-hosted
runners generally do not have IPv6, so a Linux job can run the unit tests but
not a live multi-node smoke test. That is a limit of the runner, not of this
fix, and the 467 tests above are all reachable without it.

## Why I am not opening a PR

The obvious fix is to stop applying the Linux source override under the
`mlx-cpu` extra and bump `mlx-cpu` to 0.32.0. I tried it, following the
extra-conditional marker pattern already used for `torch` in the same file, in
both an exclusive form (`extra != 'mlx-cpu'`) and a positive form
(`extra == 'mlx-cuda12'` / `'mlx-cuda13'`).

With uv 0.8.17 both forms resolve the same way: the lockfile collapses to a
single Linux resolution and the fork wheel disappears for the CUDA extras too.
That would presumably break the CUDA path, and I have no NVIDIA hardware to
check whether `mlx_cuda_12`'s libmlx pairs with the stock extension module or
only with the fork's.

Since you own the fork, you can answer that in a sentence where I can only
guess. If the stock `mlx` wheel does work with `mlx_cuda_12`, the fix is one
marker change plus a version bump. If it does not, the CPU and CUDA extras need
genuinely separate resolutions, which is a packaging decision rather than a
one-liner.

Happy to do the work either way if you tell me which it is.
```

---
_Generated by [Claude Code](https://claude.ai/code)_
