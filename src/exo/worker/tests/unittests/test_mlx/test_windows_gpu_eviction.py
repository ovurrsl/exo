from types import SimpleNamespace
from unittest import mock

from exo.shared.types.memory import Memory
from exo.utils.windows_gpu import GpuMemory
from exo.worker.engines.mlx import cache

_NO_MLX_CACHE = Memory()


def _memory_used(gpu: GpuMemory | None, mlx_cache: Memory = _NO_MLX_CACHE) -> float:
    with (
        mock.patch.object(cache, "sys", SimpleNamespace(platform="win32")),
        mock.patch.object(cache, "is_cuda_device", lambda: True),
        mock.patch.object(cache, "read_gpu_memory", lambda: gpu),
        mock.patch.object(cache.mx, "get_cache_memory", lambda: mlx_cache.in_bytes),
        mock.patch.object(cache.mx, "clear_cache"),
        mock.patch.object(
            cache.psutil, "virtual_memory", lambda: SimpleNamespace(percent=42.0)
        ),
    ):
        return cache.get_memory_used_percentage()


def _gpu(free_mb: int) -> GpuMemory:
    return GpuMemory(total=Memory.from_mb(12 * 1024), free=Memory.from_mb(free_mb))


def test_nearly_full_gpu_reads_as_full_memory():
    assert _memory_used(_gpu(free_mb=512)) == 1.0


def test_large_host_buffer_cache_cannot_mask_vram_pressure():
    # CUDA's MLX allocator counter includes pinned CPU buffers too. Even 32GiB
    # of reclaimable host cache does not provide space for a GPU KV cache.
    assert _memory_used(_gpu(free_mb=512), mlx_cache=Memory.from_mb(32768)) == 1.0


def test_gpu_cache_trim_uses_actual_driver_memory_after_trim():
    with (
        mock.patch.object(cache, "sys", SimpleNamespace(platform="win32")),
        mock.patch.object(cache, "is_cuda_device", lambda: True),
        mock.patch.object(
            cache, "read_gpu_memory", side_effect=[_gpu(512), _gpu(2048)]
        ) as read,
        mock.patch.object(cache.mx, "clear_cache") as clear,
        mock.patch.object(cache.mx, "get_cache_memory", side_effect=AssertionError),
    ):
        assert cache.get_memory_used_percentage() == 0.0
        assert read.call_count == 2
        clear.assert_called_once_with()


def test_driver_loss_after_cache_trim_still_fails_closed():
    with (
        mock.patch.object(cache, "sys", SimpleNamespace(platform="win32")),
        mock.patch.object(cache, "is_cuda_device", lambda: True),
        mock.patch.object(cache, "read_gpu_memory", side_effect=[_gpu(512), None]),
        mock.patch.object(cache.mx, "clear_cache") as clear,
    ):
        assert cache.get_memory_used_percentage() == 1.0
        clear.assert_called_once_with()


def test_healthy_driver_memory_does_not_trim_buffers():
    with (
        mock.patch.object(cache, "sys", SimpleNamespace(platform="win32")),
        mock.patch.object(cache, "is_cuda_device", lambda: True),
        mock.patch.object(cache, "read_gpu_memory", return_value=_gpu(2048)) as read,
        mock.patch.object(cache.mx, "clear_cache", side_effect=AssertionError),
        mock.patch.object(cache.mx, "get_cache_memory", side_effect=AssertionError),
    ):
        assert cache.get_memory_used_percentage() == 0.0
        assert read.call_count == 1


def test_gpu_with_room_has_no_gpu_pressure():
    assert _memory_used(_gpu(free_mb=4096)) == 0.0


def test_nvml_loss_fails_closed_on_cuda():
    assert _memory_used(None) == 1.0


def test_non_windows_memory_pressure_remains_ram_based():
    with (
        mock.patch.object(cache, "sys", SimpleNamespace(platform="darwin")),
        mock.patch.object(
            cache.psutil, "virtual_memory", lambda: SimpleNamespace(percent=42)
        ),
    ):
        assert cache.get_memory_used_percentage() == 0.42
