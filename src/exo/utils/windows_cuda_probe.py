"""Leaf subprocess entry points; importing this module never imports MLX."""

import sys
from importlib.metadata import version
from typing import Final

SUCCESS_MARKER: Final = "EXO_WINDOWS_CUDA_OK:"
SUCCESS_EXIT_CODE: Final = 7


def run_probe(stage: str) -> None:
    """Exercise CUDA and ring cleanup, including normal interpreter destruction."""
    if stage == "kernel":
        import pynvml as nvml

        from exo.utils.windows_gpu import gpu_selection_error

        nvml.nvmlInit()
        try:
            selection_error = gpu_selection_error(nvml.nvmlDeviceGetCount())
        finally:
            nvml.nvmlShutdown()
        if selection_error is not None:
            raise RuntimeError(selection_error)
    import mlx.core as mx

    if not mx.cuda.is_available():
        raise RuntimeError("The installed MLX runtime does not provide CUDA")
    mx.set_default_device(mx.gpu)
    if stage == "kernel":
        # This forces CUDA allocation, compilation, execution and a host read.
        vector = mx.arange(256, dtype=mx.float32)
        matrix = mx.reshape(vector, (16, 16))
        result = mx.sum(matrix @ mx.transpose(matrix))
        if float(result.item()) != 66672640.0:
            raise RuntimeError("CUDA matrix multiplication produced an invalid result")
    elif stage == "ring":
        group = mx.distributed.init(strict=True, backend="ring")
        if group.size() != 2:
            raise RuntimeError("The ring health check requires two ranks")
        value = mx.array([group.rank() + 1], dtype=mx.int32)
        # Transfer an actual GPU result to the CPU-stream socket collective.
        gpu_value = value + 0
        mx.eval(gpu_value)
        cpu = mx.Device(mx.cpu)
        reduced = mx.distributed.all_sum(gpu_value, group=group, stream=cpu)
        gathered = mx.distributed.all_gather(gpu_value, group=group, stream=cpu)
        mx.eval(reduced, gathered)
        if int(reduced.item()) != 3 or gathered.tolist() != [1, 2]:
            raise RuntimeError("CPU-stream ring collectives produced invalid results")
    else:
        raise ValueError(f"Unknown CUDA probe stage: {stage}")
    print(f"{SUCCESS_MARKER}{version('mlx')}", flush=True)
    # A marker without this exit code is a failed DLL/stream cleanup check.
    sys.exit(SUCCESS_EXIT_CODE)
