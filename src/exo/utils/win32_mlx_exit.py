import atexit
import sys
from collections.abc import Callable
from typing import cast


def _release_mlx_gpu_streams() -> None:
    if "mlx.core" not in sys.modules:
        return  # never imported in this process: nothing to release
    import mlx.core as mx

    # mx.clear_streams() exists at runtime but not in every mlx's type stubs.
    clear_streams = cast(Callable[[], None], getattr(mx, "clear_streams"))  # noqa: B009
    try:
        clear_streams()
    except Exception as e:  # never let an exit hook change the exit code
        print(f"exo: mx.clear_streams() at exit failed: {e!r}", file=sys.stderr)


def install_windows_mlx_exit_hook() -> None:
    """Destroy this thread's MLX GPU streams before Windows unloads CUDA.

    MLX keeps per-thread CUDA command encoders whose destructor synchronizes
    the stream. Left alive until process exit, they are destroyed during
    DLL_PROCESS_DETACH, after the CUDA driver has shut down, so the
    synchronize fails ("driver shutting down"), the C++ exception escapes a
    destructor and the process dies with 0xC0000409 (or spins forever) instead
    of exiting with its real exit code. An atexit hook runs while CUDA is still
    up. It does nothing if mlx was never imported. No-op on other platforms.
    """
    if sys.platform != "win32":
        return
    atexit.register(_release_mlx_gpu_streams)
