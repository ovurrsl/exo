"""Keep the frozen DLL layout usable without a toolkit or developer PATH."""

import os
import sys
from pathlib import Path

# Keep handles alive: closing AddDllDirectory's handle removes its directory.
_dll_directory_handles: list[object] = []
_bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
_directories = [_bundle, _bundle / "mlx"]
_nvidia = _bundle / "nvidia"
if _nvidia.is_dir():
    _directories.extend(sorted({p.parent for p in _nvidia.rglob("*.dll")}))
for _directory in _directories:
    if _directory.is_dir():
        _dll_directory_handles.append(os.add_dll_directory(str(_directory)))
os.environ["PATH"] = os.pathsep.join(
    [str(p) for p in _directories if p.is_dir()] + [os.environ.get("PATH", "")]
)
