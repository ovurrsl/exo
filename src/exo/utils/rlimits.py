import sys
import types

# Linux value of RLIMIT_NOFILE; only used by the Windows shim below.
_SHIM_RLIMIT_NOFILE = 7
_SHIM_RLIM_INFINITY = -1
# The UCRT's hard cap on open C runtime file descriptors (_setmaxstdio maximum).
_SHIM_NOFILE_LIMIT = 8192


def raise_nofile_limit(min_soft: int) -> None:
    """Raise the RLIMIT_NOFILE soft limit when the platform supports it.

    Windows does not expose POSIX resource limits; the process already inherits
    a large handle table, so this is a no-op there.
    """
    if sys.platform == "win32":
        return

    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = min(max(soft, min_soft), hard)
    resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))


def _shim_getrlimit(_limit: int) -> tuple[int, int]:
    # A finite value, so callers doing min()/max() arithmetic on the limits
    # never end up with RLIM_INFINITY (-1) as a target.
    return (_SHIM_NOFILE_LIMIT, _SHIM_NOFILE_LIMIT)


def _shim_setrlimit(_limit: int, _limits: tuple[int, int]) -> None:
    return None


def install_windows_resource_shim() -> None:
    """Let `import resource` succeed on Windows.

    mlx-lm raises its open-file limit at import time
    (`resource.setrlimit(resource.RLIMIT_NOFILE, ...)` in mlx_lm/utils.py), but
    the `resource` module only exists on POSIX, so importing mlx-lm on Windows
    fails. Windows has no per-process open-file soft limit (only the UCRT's
    8192 descriptor cap), so a module that reports that cap and ignores
    setrlimit is accurate there.
    Must run before anything imports mlx_lm. No-op on other platforms.
    """
    if sys.platform != "win32" or "resource" in sys.modules:
        return

    shim = types.ModuleType("resource", "exo shim: POSIX resource limits on Windows")
    shim.__dict__.update(
        RLIMIT_NOFILE=_SHIM_RLIMIT_NOFILE,
        RLIM_INFINITY=_SHIM_RLIM_INFINITY,
        error=OSError,
        getrlimit=_shim_getrlimit,
        setrlimit=_shim_setrlimit,
    )
    sys.modules["resource"] = shim
