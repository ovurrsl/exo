"""Offline, bounded Qwen3 host-weight staging experiment; no production admission changes."""

import argparse
import gc
import json
import os
import sys
import time
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
import psutil

from exo.utils.windows_gpu import read_gpu_memory

# isort: split
# Importing EXO above installs the Windows resource shim before mlx-lm.
from mlx_lm.models.cache import make_prompt_cache
from mlx_lm.utils import load_model

MIB = 1024**2
RESERVE = 2560 * MIB
WEIGHT_LIMIT = 128 * MIB


def arrays(tree):
    if isinstance(tree, mx.array):
        yield tree
    elif isinstance(tree, (tuple, list)):
        for item in tree:
            yield from arrays(item)
    elif isinstance(tree, dict):
        for item in tree.values():
            yield from arrays(item)


def transform(tree, function):
    if isinstance(tree, mx.array):
        return function(tree)
    if isinstance(tree, list):
        return [transform(value, function) for value in tree]
    if isinstance(tree, dict):
        return {key: transform(value, function) for key, value in tree.items()}
    raise TypeError(type(tree).__name__)


def weight_bytes(tree):
    return sum(array.nbytes for array in arrays(tree))


def gpu_free():
    memory = read_gpu_memory()
    if memory is None:
        raise RuntimeError("NVML must report an unambiguous single NVIDIA GPU")
    return memory.free.in_bytes


class Staging:
    def __init__(self, stream):
        self.stream = stream
        self.active_bytes = 0
        self.peak_bytes = 0
        self.opens = 0
        self.closes = 0
        self.lowest_free = gpu_free()

    def copy(self, source):
        # A real CUDA arithmetic output, rather than mx.array(array)'s alias.
        result = mx.add(
            source, mx.zeros_like(source, stream=self.stream), stream=self.stream
        )
        mx.eval(result)
        return result

    @contextmanager
    def stage(self, module):
        host = module.parameters()
        size = weight_bytes(host)
        if self.active_bytes + size > WEIGHT_LIMIT:
            raise RuntimeError(
                "The bounded experiment's live weight budget was exceeded"
            )
        if gpu_free() < RESERVE + 3 * size:
            raise RuntimeError("Insufficient dedicated VRAM for staging plus reserve")
        device = None
        counted = False
        try:
            device = transform(host, self.copy)
            module.update(device)
            self.active_bytes += size
            counted = True
            self.opens += 1
            self.peak_bytes = max(self.peak_bytes, self.active_bytes)
            self.lowest_free = min(self.lowest_free, gpu_free())
            yield
        finally:
            # Synchronize this stream even when layer evaluation raises.
            try:
                mx.synchronize(self.stream)
            finally:
                module.update(host)
                if counted:
                    self.active_bytes -= size
                    self.closes += 1
                device = None
                mx.clear_cache()


class StagedLayer(nn.Module):
    def __init__(self, original, staging):
        super().__init__()
        self.original = original
        self.staging = staging
        self.fail_once = False

    def __call__(self, hidden, mask=None, cache=None):
        with self.staging.stage(self.original):
            if self.fail_once:
                self.fail_once = False
                raise RuntimeError("injected-stage-failure")
            result = self.original(hidden, mask, cache)
            mx.eval(result, cache.state if cache is not None else ())
            return result


def infer(model, stream, staging=None):
    cache = make_prompt_cache(model)
    inputs = [1, 100, 200, 300]
    logits = []
    tokens = []
    for _ in range(4):
        with mx.stream(stream):
            if staging is None:
                result = model(mx.array([inputs], dtype=mx.int32), cache=cache)
                mx.eval(result, [entry.state for entry in cache])
            else:
                # Qwen3's tied head calls embed_tokens.as_linear after all blocks.
                with (
                    staging.stage(model.model.embed_tokens),
                    staging.stage(model.model.norm),
                ):
                    result = model(mx.array([inputs], dtype=mx.int32), cache=cache)
                    mx.eval(result, [entry.state for entry in cache])
            mx.synchronize(stream)
            last = np.array(result[:, -1, :].astype(mx.float32))
            logits.append(last)
            token = int(np.argmax(last, axis=-1).item())
            tokens.append(token)
            inputs = [token]
    states = [
        [np.array(value.astype(mx.float32)) for value in entry.state] for entry in cache
    ]
    offsets = [entry.offset for entry in cache]
    del cache, result
    return logits, tokens, states, offsets


def main():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    path = arguments.model.resolve(strict=True)
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    expected = {
        "model_type": "qwen3",
        "num_hidden_layers": 28,
        "hidden_size": 1024,
        "tie_word_embeddings": True,
    }
    if "model_file" in config or any(
        config.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(
            "This experiment accepts only the local Qwen3-0.6B 4-bit model"
        )
    if config.get("quantization") != {"group_size": 64, "bits": 4}:
        raise ValueError("Only affine 4-bit/group64 weights are accepted")
    files = sorted(path.glob("model*.safetensors"))
    file_bytes = sum(file.stat().st_size for file in files)
    if not files or file_bytes > 1024 * MIB:
        raise ValueError("No weights or model exceeds this experiment's 1 GiB limit")
    if sys.platform != "win32" or not mx.cuda.is_available():
        raise RuntimeError("This is a Windows CUDA hardware experiment")
    if gpu_free() < RESERVE + 3 * file_bytes:
        raise RuntimeError("Insufficient free VRAM for the small full-GPU control")
    if psutil.virtual_memory().available < 2 * file_bytes + 1024 * MIB:
        raise RuntimeError("Insufficient host RAM for this bounded experiment")
    stream = mx.new_stream(mx.gpu)
    mx.set_cache_limit(0)
    began = time.monotonic()
    free_before = gpu_free()
    with mx.stream(stream):
        baseline, _ = load_model(path, lazy=False)
    full_bytes = weight_bytes(baseline.parameters())
    reference, reference_tokens, reference_kv, reference_offsets = infer(
        baseline, stream
    )
    del baseline
    gc.collect()
    mx.synchronize(stream)
    mx.clear_cache()

    # Both Load primitives and their evaluation must belong to a CPU stream.
    with mx.stream(mx.cpu):
        model, _ = load_model(path, lazy=True)
        mx.eval(model.parameters())
    host_parameters = list(arrays(model.parameters()))
    staging = Staging(stream)
    transfer_checks = []
    for dtype in (mx.float32, mx.float16, mx.bfloat16, mx.uint32):
        with mx.stream(mx.cpu):
            host = mx.array([0, 1, 2, 63], dtype=dtype)
            mx.eval(host)
        with mx.stream(stream):
            device = staging.copy(host)
            mx.synchronize(stream)
            np.testing.assert_array_equal(
                np.array(device.astype(mx.float32)), np.array(host.astype(mx.float32))
            )
        transfer_checks.append(str(dtype))
    del host, device
    mx.clear_cache()
    layer_bytes = [weight_bytes(layer.parameters()) for layer in model.model.layers]
    resident = weight_bytes(model.model.embed_tokens.parameters()) + weight_bytes(
        model.model.norm.parameters()
    )
    assert resident + max(layer_bytes) < WEIGHT_LIMIT < full_bytes
    model.model.layers = [StagedLayer(layer, staging) for layer in model.model.layers]
    errors = []
    for _ in range(2):
        actual, tokens, actual_kv, offsets = infer(model, stream, staging)
        assert tokens == reference_tokens, "The greedy token sequence diverged"
        assert offsets == reference_offsets
        for expected_logits, actual_logits in zip(reference, actual, strict=True):
            np.testing.assert_allclose(
                actual_logits, expected_logits, atol=0.02, rtol=0.01
            )
            errors.append(float(np.max(np.abs(actual_logits - expected_logits))))
        for expected_state, actual_state in zip(reference_kv, actual_kv, strict=True):
            for expected_array, actual_array in zip(
                expected_state, actual_state, strict=True
            ):
                np.testing.assert_allclose(
                    actual_array, expected_array, atol=0.02, rtol=0.01
                )
        assert staging.active_bytes == 0 and staging.opens == staging.closes
        assert all(
            left is right
            for left, right in zip(
                host_parameters, arrays(model.parameters()), strict=True
            )
        )

    # Exceptions after staging must restore every module and release ownership.
    model.model.layers[2].fail_once = True
    try:
        infer(model, stream, staging)
    except RuntimeError as error:
        assert str(error) == "injected-stage-failure"
    else:
        raise AssertionError("The injected failure was not observed")
    assert staging.active_bytes == 0 and staging.opens == staging.closes
    assert all(
        left is right
        for left, right in zip(host_parameters, arrays(model.parameters()), strict=True)
    )
    # The same model must recover without reloading weights or recompiling wrappers.
    _, recovered, _, _ = infer(model, stream, staging)
    assert recovered == reference_tokens
    result = {
        "scope": "Small offline Qwen3 control with a 128 MiB live weight cap; not an oversized-VRAM model or production planner/ring acceptance",
        "mlx_version": version("mlx"),
        "full_model_weight_bytes": full_bytes,
        "canonical_host_weight_bytes": sum(value.nbytes for value in host_parameters),
        "resident_embedding_norm_bytes": resident,
        "largest_layer_bytes": max(layer_bytes),
        "weight_cap_bytes": WEIGHT_LIMIT,
        "observed_live_weight_peak_bytes": staging.peak_bytes,
        "stages_opened": staging.opens,
        "stages_closed": staging.closes,
        "active_weight_bytes_at_exit": staging.active_bytes,
        "greedy_tokens": reference_tokens,
        "maximum_absolute_logit_difference": max(errors),
        "transfer_dtypes": transfer_checks,
        "failure_cleanup_and_recovery": True,
        "nvml_free_before_bytes": free_before,
        "nvml_lowest_free_during_staging_bytes": staging.lowest_free,
        "nvml_free_after_bytes": gpu_free(),
        "nvml_scope": "Device-wide samples include other processes; not a per-process peak or exact host residency measurement",
        "seconds": time.monotonic() - began,
        "passed": True,
    }
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
