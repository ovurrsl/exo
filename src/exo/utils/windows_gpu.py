import os
import sys
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast, final

from exo.shared.types.memory import Memory


@final
@dataclass(frozen=True)
class GpuMemory:
    total: Memory
    free: Memory


@final
@dataclass(frozen=True)
class GpuTelemetry:
    utilization_percent: float | None
    temperature_celsius: float | None
    power_watts: float | None


class _MemoryInfo(Protocol):
    total: int
    free: int


class _UtilizationInfo(Protocol):
    gpu: int


class _NvmlApi(Protocol):
    NVMLError: type[Exception]
    NVML_TEMPERATURE_GPU: int

    # Protocol spelling must match NVIDIA's public bindings.
    nvmlInit: Callable[[], None]  # noqa: N815
    nvmlShutdown: Callable[[], None]  # noqa: N815
    nvmlDeviceGetCount: Callable[[], int]  # noqa: N815
    nvmlDeviceGetHandleByIndex: Callable[[int], object]  # noqa: N815
    nvmlDeviceGetMemoryInfo: Callable[[object], _MemoryInfo]  # noqa: N815
    nvmlDeviceGetUtilizationRates: Callable[[object], _UtilizationInfo]  # noqa: N815
    nvmlDeviceGetTemperature: Callable[[object, int], int]  # noqa: N815
    nvmlDeviceGetPowerUsage: Callable[[object], int]  # noqa: N815


def gpu_selection_error(device_count: int) -> str | None:
    """Accept only the single, unambiguously selected NVIDIA device we support."""
    if device_count != 1:
        return f"Exactly one NVIDIA GPU is required; NVML found {device_count}"
    visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
    if visible_devices not in ("", "0"):
        return "CUDA_VISIBLE_DEVICES must be unset or 0 on a single-GPU Windows node"
    return None


@final
class _GpuMemoryReader:
    """Read the sole NVIDIA device; never guess how CUDA maps several devices."""

    def __init__(self) -> None:
        self._handle: object | None = None
        self.last_total = Memory.from_bytes(0)

    def read(self) -> GpuMemory | None:
        if sys.platform != "win32":
            return None
        try:
            nvml = cast(_NvmlApi, cast(object, import_module("pynvml")))
        except (ImportError, OSError):
            return None
        try:
            if self._handle is None:
                nvml.nvmlInit()
                self._handle = nvml.nvmlDeviceGetHandleByIndex(0)
            if gpu_selection_error(nvml.nvmlDeviceGetCount()) is not None:
                return None
            info = nvml.nvmlDeviceGetMemoryInfo(self._handle)
            memory = GpuMemory(
                total=Memory.from_bytes(int(info.total)),
                free=Memory.from_bytes(int(info.free)),
            )
            if memory.total.in_bytes <= 0 or not (
                0 <= memory.free.in_bytes <= memory.total.in_bytes
            ):
                return None
            self.last_total = memory.total
            return memory
        except nvml.NVMLError:
            self._handle = None  # initialise again on the next read
            with suppress(nvml.NVMLError):
                nvml.nvmlShutdown()
            return None


_reader = _GpuMemoryReader()


def read_gpu_memory() -> GpuMemory | None:
    """Total and free memory of GPU 0 (the device MLX uses) on a Windows node.

    On a Windows CUDA node the model weights and the KV cache live in GPU
    memory, and Windows does not fail an allocation that does not fit: it
    moves it to shared system memory and generation becomes many times slower.
    So there exo reports GPU memory to the master and evicts the prefix cache
    when the GPU, not system RAM, runs low.

    None on other platforms, on ambiguous device selection, without
    nvidia-ml-py, or when NVML fails. The figures cover every process on the GPU.
    """
    return _reader.read()


def last_known_gpu_total() -> Memory:
    """A diagnostic total only: unavailable NVML must still advertise zero free."""
    return _reader.last_total


def read_gpu_telemetry() -> GpuTelemetry | None:
    """Optional GPU metrics for diagnostics; unsupported sensors remain unknown."""
    if read_gpu_memory() is None:
        return None
    nvml = cast(_NvmlApi, cast(object, import_module("pynvml")))

    try:
        handle = nvml.nvmlDeviceGetHandleByIndex(0)
    except nvml.NVMLError:
        return None
    utilization: float | None = None
    temperature: float | None = None
    power: float | None = None
    with suppress(nvml.NVMLError):
        utilization = float(nvml.nvmlDeviceGetUtilizationRates(handle).gpu)
    with suppress(nvml.NVMLError):
        temperature = float(
            nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
        )
    with suppress(nvml.NVMLError):
        power = float(nvml.nvmlDeviceGetPowerUsage(handle)) / 1000
    return GpuTelemetry(utilization, temperature, power)
