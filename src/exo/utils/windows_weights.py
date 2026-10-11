"""Validate actual owned MLX parameter bytes before Windows CUDA materialization."""

import sys
from collections.abc import Sequence
from typing import cast

import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_flatten

from exo.utils.windows_gpu import read_gpu_memory

_RUNTIME_RESERVE_BYTES = 2560 * 1024 * 1024


def parameter_bytes(module: nn.Module) -> int:
    parameters = cast(list[tuple[str, mx.array]], tree_flatten(module.parameters()))
    seen: set[int] = set()
    total = 0
    for _name, parameter in parameters:
        if id(parameter) not in seen:
            seen.add(id(parameter))
            total += parameter.nbytes
    return total


def validate_windows_weight_budget(
    model: nn.Module,
    all_layers: Sequence[object] | None = None,
    owned_layers: Sequence[object] | None = None,
) -> None:
    if sys.platform != "win32":
        return
    needed = parameter_bytes(model)
    if all_layers is not None and owned_layers is not None:

        def layer_bytes(layer: object) -> int:
            if not isinstance(layer, nn.Module):
                raise TypeError("Windows weight accounting requires MLX module layers")
            return parameter_bytes(layer)

        needed -= sum(layer_bytes(layer) for layer in all_layers)
        needed += sum(layer_bytes(layer) for layer in owned_layers)
    memory = read_gpu_memory()
    if memory is None:
        raise RuntimeError(
            "NVIDIA memory capacity became unavailable before loading weights"
        )
    # CUDA MLX's allocator also counts pinned host buffers. Adding its active
    # bytes to NVML free capacity can turn CPU weights into fictional VRAM.
    # This guard runs before materialization, so use remaining device capacity.
    available = memory.free.in_bytes - _RUNTIME_RESERVE_BYTES
    if needed > available:
        raise MemoryError(
            "Windows rank weights (including replicated components) do not fit: "
            f"{needed / 2**30:.2f} GiB needed, {max(0, available) / 2**30:.2f} GiB "
            "available after the 2.5 GiB runtime/KV reserve"
        )
