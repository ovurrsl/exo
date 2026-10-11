# Build from the repository root using the tested Windows CUDA environment.
import importlib.util
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

if sys.platform != "win32":
    raise SystemExit("This spec builds the Windows runtime only.")
ROOT = Path(SPECPATH).resolve().parents[1]
PACKAGING = ROOT / "packaging" / "windows"
SOURCE = ROOT / "src"
SITE = Path(importlib.util.find_spec("mlx").submodule_search_locations[0]).parent
MLX = SITE / "mlx"
NVIDIA = SITE / "nvidia"
for required in [ROOT / "dashboard/build/index.html", MLX / "mlx.dll",
                 MLX / "include/cccl", NVIDIA / "cu13/include/cuda.h",
                 NVIDIA / "cu13/bin/x86_64/nvrtc64_130_0.dll",
                 NVIDIA / "cudnn/bin/cudnn64_9.dll"]:
    if not required.exists():
        raise SystemExit(f"Required Windows runtime asset is absent: {required}")

# Preserve mlx.dll -> ../nvidia/cu13 and the runtime NVRTC include search paths.
# Listing DLLs as binaries also asks PyInstaller to include their VC dependencies.
binaries = [(str(p), "mlx") for p in MLX.glob("*.dll")]
binaries += [(str(p), str(p.parent.relative_to(SITE)))
             for p in NVIDIA.rglob("*.dll")]
datas = [(str(ROOT / "dashboard/build"), "dashboard"),
         (str(ROOT / "resources"), "resources"),
         (str(SOURCE / "exo/shared/models"), "exo/shared/models"),
         (str(MLX / "include"), "mlx/include"),
         (str(NVIDIA / "cu13/include"), "nvidia/cu13/include")]
if (MLX / "share").is_dir():
    datas.append((str(MLX / "share"), "mlx/share"))
for package in ["exo", "mlx", "mlx-lm", "mlx-vlm", "transformers",
                "huggingface-hub", "tiktoken", "tokenizers", "safetensors"]:
    datas += copy_metadata(package)
for package in ["nvidia-cublas", "nvidia-cuda-nvrtc", "nvidia-cuda-runtime",
                "nvidia-cudnn-cu13", "nvidia-cufft", "nvidia-cusolver",
                "nvidia-cusparse", "nvidia-nvjitlink"]:
    datas += copy_metadata(package)
hiddenimports = ["check_mlx", "exo_rs", "tiktoken_ext.openai_public"]
def module_files(package):
    # mlx-lm/vlm import POSIX resource at module load; Exo installs its Windows
    # shim before runtime import. Enumerate dynamic model modules without importing
    # them inside PyInstaller's isolated discovery process.
    spec = importlib.util.find_spec(package)
    directory = Path(spec.submodule_search_locations[0])
    result = [package]
    for path in directory.rglob("*.py"):
        parts = path.relative_to(directory).with_suffix("").parts
        if "tests" in parts:
            continue
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            result.append(".".join((package, *parts)))
    return result

for package in ["mlx", "mlx_lm", "mlx_vlm", "transformers"]:
    hiddenimports += module_files(package)
# Optional image/vision backends are collected when installed in the pinned build env.
for package in ["mflux", "torch", "torchvision", "torchaudio"]:
    if importlib.util.find_spec(package) is not None:
        hiddenimports += module_files(package)
        datas += copy_metadata(package)
        if package == "mflux":
            datas += collect_data_files(package)

a = Analysis([str(PACKAGING / "entrypoint.py")],
             pathex=[str(SOURCE), str(PACKAGING), str(ROOT / "scripts/windows/mlx")],
             binaries=binaries, datas=datas, hiddenimports=sorted(set(hiddenimports)),
             runtime_hooks=[str(PACKAGING / "runtime_hook.py")],
             excludes=["pytest", "IPython", "matplotlib.tests"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="exo", console=True,
          debug=False, strip=False, upx=False, bootloader_ignore_signals=False)
coll = COLLECT(exe, a.binaries, a.datas, name="exo", strip=False, upx=False)
