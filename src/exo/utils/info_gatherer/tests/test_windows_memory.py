import sys
from unittest import mock

import psutil

from exo.shared.types.memory import Memory
from exo.shared.types.profiling import MemoryUsage
from exo.utils.info_gatherer import info_gatherer
from exo.utils.windows_gpu import GpuMemory

_GIB = 1024**3


def _gather(gpu: GpuMemory | None, override_memory: int | None) -> MemoryUsage:
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(info_gatherer, "read_gpu_memory", lambda: gpu),
    ):
        return info_gatherer.gather_memory_usage(override_memory)


def _gpu(total: int, free: int) -> GpuMemory:
    return GpuMemory(total=Memory.from_bytes(total), free=Memory.from_bytes(free))


def test_cuda_node_reports_gpu_memory_minus_the_reserve():
    usage = _gather(_gpu(total=12 * _GIB, free=9 * _GIB), override_memory=None)

    reserve = info_gatherer.WINDOWS_GPU_MEMORY_RESERVE.in_bytes
    assert usage.ram_total == Memory.from_bytes(12 * _GIB)
    assert usage.ram_available == Memory.from_bytes(9 * _GIB - reserve)


def test_reported_gpu_memory_is_never_negative():
    usage = _gather(_gpu(total=12 * _GIB, free=_GIB), override_memory=None)

    assert usage.ram_available == Memory.from_bytes(0)


def test_override_memory_can_reduce_the_gpu_budget():
    usage = _gather(_gpu(total=12 * _GIB, free=9 * _GIB), 5 * _GIB)
    assert usage.ram_available == Memory.from_bytes(5 * _GIB)
    assert usage.ram_total == Memory.from_bytes(12 * _GIB)


def test_override_cannot_exceed_physical_gpu_budget():
    usage = _gather(_gpu(total=12 * _GIB, free=9 * _GIB), 100 * _GIB)
    assert usage.ram_available.in_bytes == (
        9 * _GIB - info_gatherer.WINDOWS_GPU_MEMORY_RESERVE.in_bytes
    )


def test_without_a_gpu_advertises_zero_capacity():
    usage = _gather(None, override_memory=None)
    assert usage.ram_available.in_bytes == 0


def test_override_cannot_reenable_a_lost_gpu():
    assert _gather(None, override_memory=100 * _GIB).ram_available.in_bytes == 0


def test_swap_failure_reports_zero_swap_without_falling_back_to_ram():
    with mock.patch.object(psutil, "swap_memory", side_effect=OSError("unavailable")):
        usage = _gather(_gpu(total=12 * _GIB, free=9 * _GIB), None)
    assert usage.ram_total.in_bytes == 12 * _GIB
    assert usage.swap_total.in_bytes == usage.swap_available.in_bytes == 0


def test_non_windows_override_and_ram_behavior_is_preserved():
    with mock.patch.object(sys, "platform", "darwin"):
        usage = info_gatherer.gather_memory_usage(5 * _GIB)
    assert usage.ram_total == Memory.from_bytes(psutil.virtual_memory().total)
    assert usage.ram_available == Memory.from_bytes(5 * _GIB)
