import sys
import types
from unittest import mock

from exo.shared.types.memory import Memory
from exo.utils.windows_gpu import (
    GpuMemory,
    _GpuMemoryReader,  # pyright: ignore[reportPrivateUsage]
)


class _NvmlError(Exception):
    pass


class _FakeNvml:
    """Records NVML calls; `failing` makes the next memory query fail."""

    def __init__(self, total: int, free: int) -> None:
        self.total = total
        self.free = free
        self.inits = 0
        self.failing = False

    def module(self) -> types.ModuleType:
        nvml = types.ModuleType("pynvml")
        nvml.__dict__.update(
            NVMLError=_NvmlError,
            nvmlInit=self._init,
            nvmlDeviceGetHandleByIndex=self._handle_by_index,
            nvmlDeviceGetMemoryInfo=self._memory_info,
        )
        return nvml

    def _init(self) -> None:
        self.inits += 1

    def _handle_by_index(self, index: int) -> str:
        return f"gpu{index}"

    def _memory_info(self, handle: str) -> types.SimpleNamespace:
        assert handle == "gpu0"
        if self.failing:
            raise _NvmlError("GPU lost")
        return types.SimpleNamespace(total=self.total, free=self.free)


def _read(reader: _GpuMemoryReader, platform: str, nvml: _FakeNvml) -> GpuMemory | None:
    with (
        mock.patch.object(sys, "platform", platform),
        mock.patch.dict(sys.modules, {"pynvml": nvml.module()}),
    ):
        return reader.read()


def test_reads_gpu_memory_on_windows():
    nvml = _FakeNvml(total=12 * 1024**3, free=9 * 1024**3)

    assert _read(_GpuMemoryReader(), "win32", nvml) == GpuMemory(
        total=Memory.from_bytes(12 * 1024**3), free=Memory.from_bytes(9 * 1024**3)
    )


def test_does_nothing_on_other_platforms():
    nvml = _FakeNvml(total=1, free=1)

    assert _read(_GpuMemoryReader(), "darwin", nvml) is None
    assert _read(_GpuMemoryReader(), "linux", nvml) is None
    assert nvml.inits == 0


def test_initialises_nvml_once():
    nvml = _FakeNvml(total=8, free=4)
    reader = _GpuMemoryReader()

    _read(reader, "win32", nvml)
    _read(reader, "win32", nvml)

    assert nvml.inits == 1


def test_nvml_failure_reads_as_unknown_and_retries():
    nvml = _FakeNvml(total=8, free=4)
    reader = _GpuMemoryReader()
    _read(reader, "win32", nvml)

    nvml.failing = True
    assert _read(reader, "win32", nvml) is None

    nvml.failing = False
    assert _read(reader, "win32", nvml) is not None
    assert nvml.inits == 2


def test_without_nvidia_ml_py_reads_as_unknown():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.dict(sys.modules, {"pynvml": None}),
    ):
        assert _GpuMemoryReader().read() is None
