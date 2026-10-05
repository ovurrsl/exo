import sys
from dataclasses import dataclass
from typing import final

from exo.shared.types.memory import Memory


@final
@dataclass(frozen=True)
class GpuMemory:
    total: Memory
    free: Memory


@final
class _GpuMemoryReader:
    """Reads GPU 0's memory through NVML, initialising NVML on first use."""

    def __init__(self) -> None:
        self._handle: object | None = None

    def read(self) -> GpuMemory | None:
        if sys.platform != "win32":
            return None
        try:
            import pynvml as nvml  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            return None
        try:
            if self._handle is None:
                nvml.nvmlInit()
                self._handle = nvml.nvmlDeviceGetHandleByIndex(0)
            info = nvml.nvmlDeviceGetMemoryInfo(self._handle)
            return GpuMemory(
                total=Memory.from_bytes(int(info.total)),
                free=Memory.from_bytes(int(info.free)),
            )
        except nvml.NVMLError:
            self._handle = None  # initialise again on the next read
            return None


_reader = _GpuMemoryReader()


def read_gpu_memory() -> GpuMemory | None:
    """Total and free memory of GPU 0 (the device MLX uses) on a Windows node.

    On a Windows CUDA node the model weights and the KV cache live in GPU
    memory, and Windows does not fail an allocation that does not fit: it
    moves it to shared system memory and generation becomes many times slower.
    So there exo reports GPU memory to the master and evicts the prefix cache
    when the GPU, not system RAM, runs low.

    None on other platforms, without nvidia-ml-py, or when NVML fails. The
    figures cover every process on the GPU, as nvidia-smi shows them.
    """
    return _reader.read()
