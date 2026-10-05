from types import SimpleNamespace
from unittest import mock

from exo.shared.types.memory import Memory
from exo.utils.windows_gpu import GpuMemory
from exo.worker.engines.mlx import cache


def _memory_used(gpu: GpuMemory | None) -> float:
    with (
        mock.patch.object(cache, "read_gpu_memory", lambda: gpu),
        mock.patch.object(
            cache.psutil, "virtual_memory", lambda: SimpleNamespace(percent=42.0)
        ),
    ):
        return cache.get_memory_used_percentage()


def _gpu(free_mb: int) -> GpuMemory:
    return GpuMemory(total=Memory.from_mb(12 * 1024), free=Memory.from_mb(free_mb))


def test_nearly_full_gpu_reads_as_full_memory():
    assert _memory_used(_gpu(free_mb=512)) == 1.0


def test_gpu_with_room_leaves_the_system_ram_figure():
    assert _memory_used(_gpu(free_mb=4096)) == 0.42


def test_without_a_gpu_reading_system_ram_decides():
    assert _memory_used(None) == 0.42
