from importlib.metadata import version

from exo.utils.rlimits import install_windows_resource_shim
from exo.utils.win32_mlx_exit import install_windows_mlx_exit_hook

# mlx-lm imports the POSIX-only `resource` module. Install the Windows shim
# before anything in this package (runner processes, tests) can import mlx-lm.
# No-op on other platforms.
install_windows_resource_shim()
# Registered before mlx is imported, so it runs after mlx's own atexit hooks.
install_windows_mlx_exit_hook()

__version__ = version("exo")
