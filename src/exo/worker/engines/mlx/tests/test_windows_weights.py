import sys

import mlx.core as mx
import mlx.nn as nn
import pytest

from exo.shared.types.memory import Memory
from exo.utils import windows_weights
from exo.utils.windows_gpu import GpuMemory


def test_actual_parameters_include_replicated_weights() -> None:
    with mx.stream(mx.Device(mx.cpu)):
        model = nn.Linear(128, 128)
    assert windows_weights.parameter_bytes(model) == (128 * 128 + 128) * 4


def test_gpu_loss_and_foreign_vram_pressure_fail_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mx.stream(mx.Device(mx.cpu)):
        model = nn.Linear(128, 128)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(windows_weights, "read_gpu_memory", lambda: None)
    with pytest.raises(RuntimeError, match="unavailable"):
        windows_weights.validate_windows_weight_budget(model)
    monkeypatch.setattr(
        windows_weights,
        "read_gpu_memory",
        lambda: GpuMemory(Memory.from_gb(12), Memory.from_bytes(2560 * 1024**2 + 1024)),
    )
    # Large CPU/pinned-host allocations are included in MLX's allocator total;
    # they must never be counted as available device capacity.
    monkeypatch.setattr(mx, "get_active_memory", lambda: 16 * 1024**3)
    with pytest.raises(MemoryError, match="replicated"):
        windows_weights.validate_windows_weight_budget(model)


def test_mac_path_does_not_query_nvml(monkeypatch: pytest.MonkeyPatch) -> None:
    with mx.stream(mx.Device(mx.cpu)):
        model = nn.Linear(4, 4)
    monkeypatch.setattr(sys, "platform", "darwin")

    def fail_if_called() -> GpuMemory:
        raise AssertionError("Mac must not query NVIDIA capacity")

    monkeypatch.setattr(windows_weights, "read_gpu_memory", fail_if_called)
    windows_weights.validate_windows_weight_budget(model)
