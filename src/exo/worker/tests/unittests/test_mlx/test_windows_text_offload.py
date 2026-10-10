import os
import sys
from collections.abc import Callable, Iterator
from typing import cast

import mlx.core as mx
import mlx.nn as nn
import numpy as np
import pytest
from mlx_lm.models.cache import KVCache
from mlx_lm.models.qwen3 import Model as Qwen3Model
from mlx_lm.models.qwen3 import ModelArgs

from exo.shared.types.memory import Memory
from exo.utils.windows_gpu import GpuMemory
from exo.worker.engines.mlx import windows_text_offload as offload


def _model(layer_count: int = 2) -> nn.Module:
    with mx.stream(mx.Device(mx.cpu)):
        mx.random.seed(7)
        arguments = ModelArgs(
            model_type="qwen3",
            hidden_size=64,
            num_hidden_layers=layer_count,
            intermediate_size=128,
            num_attention_heads=4,
            num_key_value_heads=2,
            rms_norm_eps=1e-6,
            vocab_size=128,
            max_position_embeddings=128,
            rope_theta=10000.0,
            head_dim=16,
            tie_word_embeddings=True,
        )
        model = cast(nn.Module, Qwen3Model(arguments))
        nn.quantize(model, group_size=32, bits=4)
        mx.eval(model.parameters())
        return model


def _prepare(
    model: nn.Module,
    policy: offload.WindowsTextOffloadPolicy,
    *,
    world_size: int = 1,
    vision: bool = False,
) -> offload.WindowsQwen3OffloadModel:
    return offload.prepare_windows_qwen3_offload(
        model, policy, world_size=world_size, vision=vision, cpu_loaded=True
    )


def _policy() -> offload.WindowsTextOffloadPolicy:
    return offload.WindowsTextOffloadPolicy(
        enabled=True,
        host_limit_bytes=16 * 1024**2,
        stage_limit_bytes=1024**2,
        host_reserve_bytes=0,
        gpu_reserve_bytes=1024,
        max_prefill_tokens=16,
        max_context_tokens=32,
    )


@pytest.fixture
def cpu_staging(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(mx.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        offload, "_new_gpu_stream", lambda: mx.new_stream(mx.Device(mx.cpu))
    )
    monkeypatch.setattr(offload, "_host_available_bytes", lambda: 1024**3)
    monkeypatch.setattr(
        offload,
        "read_gpu_memory",
        lambda: GpuMemory(Memory.from_gb(12), Memory.from_gb(10)),
    )
    with mx.stream(mx.Device(mx.cpu)):
        yield


def test_opt_in_is_required_before_capacity_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_query() -> GpuMemory:
        raise AssertionError("Disabled policy must not query GPU")

    monkeypatch.setattr(offload, "read_gpu_memory", reject_query)
    with pytest.raises(ValueError, match="opt-in"):
        _prepare(_model(), offload.WindowsTextOffloadPolicy())


@pytest.mark.parametrize("world_size,vision", [(2, False), (1, True)])
def test_distributed_and_vision_are_rejected(
    cpu_staging: None, world_size: int, vision: bool
) -> None:
    with pytest.raises(ValueError, match="single|vision"):
        _prepare(_model(), _policy(), world_size=world_size, vision=vision)


def test_non_qwen_architecture_is_rejected(cpu_staging: None) -> None:
    with pytest.raises(ValueError, match="Qwen3"):
        _prepare(nn.Linear(4, 4), _policy())


def test_unsupported_cpu_head_quantization_is_rejected(cpu_staging: None) -> None:
    model = _model()
    embedding = cast(offload._QwenModel, cast(object, model)).model.embed_tokens  # pyright: ignore[reportPrivateUsage]
    cast(offload._Quantization, cast(object, embedding)).mode = "mxfp4"  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ValueError, match="quantization"):
        _prepare(model, _policy())


def test_host_and_gpu_limits_use_independent_capacity(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _model()
    monkeypatch.setattr(offload, "_host_available_bytes", lambda: 1)
    with pytest.raises(MemoryError, match="host"):
        _prepare(model, _policy())
    monkeypatch.setattr(offload, "_host_available_bytes", lambda: 1024**3)
    monkeypatch.setattr(offload, "read_gpu_memory", lambda: None)
    monkeypatch.setattr(mx, "get_active_memory", lambda: 100 * 1024**3)
    with pytest.raises(MemoryError, match="VRAM|NVIDIA"):
        _prepare(model, _policy())


def test_incremental_host_plan_fits_when_two_full_copies_do_not(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _model(16)
    inner = cast(offload._QwenModel, cast(object, model)).model  # pyright: ignore[reportPrivateUsage]
    needed = offload.parameter_bytes(model)
    largest = max(
        offload.parameter_bytes(component)
        for component in (inner.embed_tokens, inner.norm, *inner.layers)
    )
    available = needed + 6 * largest + 64
    assert available < 2 * needed
    monkeypatch.setattr(offload, "_host_available_bytes", lambda: available)
    wrapped = _prepare(model, _policy())
    assert wrapped.canonical_host_weight_bytes == needed
    assert len(wrapped.layers) == 16


def test_trusted_cpu_loader_is_required(cpu_staging: None) -> None:
    with pytest.raises(ValueError, match="trusted CPU-stream loader"):
        offload.prepare_windows_qwen3_offload(_model(), _policy())


def test_component_copy_preserves_aliases_and_has_scoped_memo(
    cpu_staging: None,
) -> None:
    modules = [nn.Module(), nn.Module()]
    for index, module in enumerate(modules):
        value = mx.array([index + 1], dtype=mx.bfloat16)
        module["first"] = value
        module["alias"] = value
        offload._canonicalize_component(module)  # pyright: ignore[reportPrivateUsage]
        first = cast(mx.array, module["first"])
        alias = cast(mx.array, module["alias"])
        assert first is alias
        assert first is not value
        assert int(first.item()) == index + 1


def _forward(model: nn.Module, tokens: list[int], cache: list[KVCache]) -> mx.array:
    forward = cast(Callable[..., mx.array], model)
    result = forward(mx.array([tokens]), cache=cache)
    mx.eval(
        result,
        *[value for entry in cache for value in entry.state if value is not None],
    )
    return result


def test_cpu_outer_matches_reference_and_restores_parameters(cpu_staging: None) -> None:
    model = _model()
    reference_cache = [KVCache(), KVCache()]
    reference = [
        _forward(model, tokens, reference_cache) for tokens in ([1, 2, 3], [4], [5])
    ]
    wrapped = _prepare(model, _policy())
    original_parameters = wrapped.host_parameters
    actual_cache = [KVCache(), KVCache()]
    for tokens, expected in zip(([1, 2, 3], [4], [5]), reference, strict=True):
        actual = _forward(wrapped, tokens, actual_cache)
        np.testing.assert_allclose(
            np.array(actual), np.array(expected), atol=1e-5, rtol=1e-5
        )
        assert wrapped.active_layer is None
        assert wrapped.host_parameters is original_parameters
    assert wrapped.stages_opened == wrapped.stages_closed == 6
    assert [entry.offset for entry in actual_cache] == [5, 5]
    for expected, actual in zip(reference_cache, actual_cache, strict=True):
        for a, b in zip(expected.state, actual.state, strict=True):
            np.testing.assert_allclose(np.array(a), np.array(b), atol=1e-5, rtol=1e-5)


def test_batch_and_long_context_are_rejected(cpu_staging: None) -> None:
    wrapped = _prepare(_model(), _policy())
    with pytest.raises(ValueError, match="batch"):
        wrapped(mx.array([[1], [2]]), cache=[KVCache(), KVCache()])
    with pytest.raises(ValueError, match="prefill"):
        wrapped(mx.array([list(range(17))]), cache=[KVCache(), KVCache()])
    cache = [KVCache(), KVCache()]
    cache[0].offset = 32
    with pytest.raises(ValueError, match="context"):
        wrapped(mx.array([[1]]), cache=cache)


def test_host_copy_preserves_packed_integer_and_bfloat16(cpu_staging: None) -> None:
    for dtype in (mx.uint32, mx.bfloat16, mx.float16, mx.float32):
        original = mx.array([0, 1, 63, 127], dtype=dtype)
        copied = offload._host_copy(original)  # pyright: ignore[reportPrivateUsage]
        mx.eval(copied)
        assert copied.dtype == dtype
        assert copied is not original
        np.testing.assert_array_equal(
            np.array(copied.astype(mx.float32)), np.array(original.astype(mx.float32))
        )


def _exercise_failure_and_recovery(
    wrapped: offload.WindowsQwen3OffloadModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging_type = type(wrapped.staging)
    copy = staging_type.copy_to_device
    failed = False

    def fail_after_staging(staging: offload._LayerStaging, value: mx.array) -> mx.array:  # pyright: ignore[reportPrivateUsage]
        nonlocal failed
        if staging.active_layer is not None and not failed:
            failed = True
            raise RuntimeError("injected-stage-failure")
        return copy(staging, value)

    with monkeypatch.context() as scoped:
        scoped.setattr(staging_type, "copy_to_device", fail_after_staging)
        with pytest.raises(RuntimeError, match="injected-stage-failure"):
            _forward(wrapped, [1, 2, 3], [KVCache(), KVCache()])
    assert wrapped.active_layer is None
    assert wrapped.stages_opened == wrapped.stages_closed
    for layer in wrapped.staging.layers:
        actual = list(offload._arrays(layer.module.parameters()))  # pyright: ignore[reportPrivateUsage]
        expected = list(offload._arrays(layer.host_parameters))  # pyright: ignore[reportPrivateUsage]
        assert all(a is b for a, b in zip(actual, expected, strict=True))
    _forward(wrapped, [1, 2, 3], [KVCache(), KVCache()])
    assert wrapped.active_layer is None
    assert wrapped.stages_opened == wrapped.stages_closed


def test_stage_failure_restores_host_weights_and_recovers(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapped = _prepare(_model(), _policy())
    _exercise_failure_and_recovery(wrapped, monkeypatch)


def test_partial_weight_copy_failure_keeps_canonical_host_parameters(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapped = _prepare(_model(), _policy())
    staging_type = type(wrapped.staging)
    copy = staging_type.copy_to_device
    copies = 0

    def fail_second_copy(staging: offload._LayerStaging, value: mx.array) -> mx.array:  # pyright: ignore[reportPrivateUsage]
        nonlocal copies
        copies += 1
        if copies == 2:
            raise RuntimeError("injected-copy-failure")
        return copy(staging, value)

    with monkeypatch.context() as scoped:
        scoped.setattr(staging_type, "copy_to_device", fail_second_copy)
        with pytest.raises(RuntimeError, match="injected-copy-failure"):
            _forward(wrapped, [1], [KVCache(), KVCache()])
    assert wrapped.active_layer is None
    assert wrapped.stages_opened == wrapped.stages_closed == 0
    for layer in wrapped.staging.layers:
        actual = list(offload._arrays(layer.module.parameters()))  # pyright: ignore[reportPrivateUsage]
        expected = list(offload._arrays(layer.host_parameters))  # pyright: ignore[reportPrivateUsage]
        assert all(a is b for a, b in zip(actual, expected, strict=True))
    _forward(wrapped, [1], [KVCache(), KVCache()])


def test_foreign_gpu_pressure_is_rechecked_before_forward(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapped = _prepare(_model(), _policy())
    monkeypatch.setattr(offload, "read_gpu_memory", lambda: None)
    with pytest.raises(MemoryError, match="VRAM"):
        _forward(wrapped, [1], [KVCache(), KVCache()])
    assert wrapped.active_layer is None
    assert wrapped.stages_opened == wrapped.stages_closed == 0


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("EXO_TEST_WINDOWS_TEXT_OFFLOAD_GPU") != "1",
    reason="Explicit isolated GPU acceptance required",
)
def test_windows_gpu_staging_matches_tiny_qwen3_cpu_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _model()
    reference_cache = [KVCache(), KVCache()]
    reference = [
        _forward(model, tokens, reference_cache) for tokens in ([1, 2, 3], [4], [5])
    ]
    wrapped = _prepare(model, _policy())
    actual_cache = [KVCache(), KVCache()]
    for tokens, expected in zip(([1, 2, 3], [4], [5]), reference, strict=True):
        actual = _forward(wrapped, tokens, actual_cache)
        np.testing.assert_allclose(
            np.array(actual), np.array(expected), atol=0.02, rtol=0.01
        )
        assert wrapped.active_layer is None
    assert wrapped.stages_opened == wrapped.stages_closed == 6
    for expected, actual in zip(reference_cache, actual_cache, strict=True):
        for a, b in zip(expected.state, actual.state, strict=True):
            np.testing.assert_allclose(np.array(a), np.array(b), atol=0.02, rtol=0.01)
    _exercise_failure_and_recovery(wrapped, monkeypatch)
