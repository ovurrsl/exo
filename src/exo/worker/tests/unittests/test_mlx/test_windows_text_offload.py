import os
import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
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

_mock_gpu_budget: list[int] | None = None
_prepared_models: list[offload.WindowsQwen3OffloadModel] | None = None


def _overflow_capacity(
    model: nn.Module, policy: offload.WindowsTextOffloadPolicy
) -> int:
    original = cast(offload._QwenModel, cast(object, model))  # pyright: ignore[reportPrivateUsage]
    args = cast(ModelArgs, original.args)
    parameters = offload._arrays(  # pyright: ignore[reportPrivateUsage]
        cast(offload.ParameterTree, original.model.layers[0].parameters())
    )
    item_size = max(
        4 if value.dtype == mx.float32 else 2
        for value in parameters
        if mx.issubdtype(value.dtype, mx.floating)
    )
    layer_kv = (
        2
        * args.num_key_value_heads
        * args.head_dim
        * (policy.max_context_tokens + 255)
        * item_size
    )
    head = (
        original.model.embed_tokens
        if args.tie_word_embeddings
        else cast(nn.Module, model["lm_head"])
    )
    required = (
        offload.parameter_bytes(head)
        + offload.parameter_bytes(original.model.norm)
        + 3 * max(offload.parameter_bytes(layer) for layer in original.model.layers)
    )
    return (
        256 * 1024**2  # Physical headroom is planning-only, separate from reserves.
        + policy.gpu_reserve_bytes
        + layer_kv * (len(original.model.layers) + 2)
        + max(required, 3 * offload.parameter_bytes(head))
    )


def _model(
    layer_count: int = 2,
    *,
    tie_word_embeddings: bool = True,
    dtype: mx.Dtype = mx.float32,
    group_size: int = 32,
    hidden_size: int = 64,
) -> nn.Module:
    with mx.stream(mx.Device(mx.cpu)):
        mx.random.seed(7)
        arguments = ModelArgs(
            model_type="qwen3",
            hidden_size=hidden_size,
            num_hidden_layers=layer_count,
            intermediate_size=128,
            num_attention_heads=4,
            num_key_value_heads=2,
            rms_norm_eps=1e-6,
            vocab_size=128,
            max_position_embeddings=128,
            rope_theta=10000.0,
            head_dim=16,
            tie_word_embeddings=tie_word_embeddings,
        )
        model = cast(nn.Module, Qwen3Model(arguments))
        model.set_dtype(dtype)  # pyright: ignore[reportUnknownMemberType]
        nn.quantize(model, group_size=group_size, bits=4)
        mx.eval(model.parameters())
        return model


def _prepare(
    model: nn.Module,
    policy: offload.WindowsTextOffloadPolicy,
    *,
    world_size: int = 1,
    vision: bool = False,
) -> offload.WindowsQwen3OffloadModel:
    if _mock_gpu_budget is not None and isinstance(model, Qwen3Model):
        _mock_gpu_budget[0] = _overflow_capacity(model, policy)
    wrapped = offload.prepare_windows_qwen3_offload(
        model, policy, world_size=world_size, vision=vision, cpu_loaded=True
    )
    if _prepared_models is not None:
        _prepared_models.append(wrapped)
    return wrapped


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
    prepared: list[offload.WindowsQwen3OffloadModel] = []
    monkeypatch.setattr(sys.modules[__name__], "_prepared_models", prepared)
    budget = [0]
    monkeypatch.setattr(sys.modules[__name__], "_mock_gpu_budget", budget)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(mx.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        offload, "_new_gpu_stream", lambda: mx.new_stream(mx.Device(mx.cpu))
    )
    monkeypatch.setattr(offload, "_host_available_bytes", lambda: 1024**3)
    monkeypatch.setattr(
        offload,
        "read_gpu_memory",
        lambda: GpuMemory(Memory.from_gb(12), Memory.from_bytes(budget[0])),
    )
    with mx.stream(mx.Device(mx.cpu)):
        try:
            yield
        finally:
            for wrapped in prepared:
                wrapped.close()


def test_high_capacity_residency_releases_all_host_owners(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        offload,
        "read_gpu_memory",
        lambda: GpuMemory(Memory.from_gb(12), Memory.from_gb(10)),
    )
    wrapped = _prepare(_model(tie_word_embeddings=False), _policy())
    assert wrapped.canonical_host_weight_bytes == 0
    assert "host_parameters" not in wrapped
    assert wrapped.residency_plan.overflow_component_ids == ()
    assert all(layer.host_parameters is None for layer in wrapped.staging.layers)
    _forward(wrapped, [1, 2], [KVCache(), KVCache()])
    assert wrapped.stages_opened == wrapped.stages_closed == 0


def test_overflow_ownership_excludes_resident_tied_head(cpu_staging: None) -> None:
    model = _model()
    original = cast(offload._QwenModel, cast(object, model))  # pyright: ignore[reportPrivateUsage]
    decoder_bytes = sum(
        offload.parameter_bytes(layer) for layer in original.model.layers
    )
    wrapped = _prepare(model, _policy())
    assert wrapped.canonical_host_weight_bytes == decoder_bytes
    assert wrapped.residency_plan.resident_component_ids == ("head", "norm")
    assert wrapped.residency_plan.overflow_component_ids == ("layer0", "layer1")


def test_mandatory_gpu_head_fails_instead_of_cpu_fallback(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        offload,
        "read_gpu_memory",
        lambda: GpuMemory(Memory.from_gb(12), Memory.from_bytes(1)),
    )
    with pytest.raises(MemoryError, match="GPU|VRAM"):
        _prepare(_model(), _policy())


def test_owned_cache_credit_uses_capacity_and_resets_on_settle(
    cpu_staging: None,
) -> None:
    wrapped = _prepare(_model(), _policy())
    cache = [KVCache(), KVCache()]
    _forward(wrapped, [1, 2, 3], cache)
    capacities: list[int] = []
    for entry in cache:
        assert entry.keys is not None and entry.values is not None
        capacities.append(entry.keys.nbytes + entry.values.nbytes)
    assert wrapped.staging.cache_credits == capacities
    assert capacities[0] > 3 * 2 * 2 * 16 * 4
    for entry in cache:
        entry.trim(2)
    _forward(wrapped, [4], cache)
    assert wrapped.staging.cache_credits == capacities
    wrapped.settle_request()
    assert wrapped.staging.cache_credits == [0, 0]
    assert wrapped.staging.cache_pool_ids is None


def test_materialized_kv_is_not_counted_twice_in_live_capacity(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapped = _prepare(_model(), _policy())
    cache = [KVCache(), KVCache()]
    _forward(wrapped, [1], cache)
    one_cache = wrapped.staging.cache_credits[0]
    layer_bytes = wrapped.staging.layers[0].bytes
    free = (
        wrapped.residency_plan.reserve_bytes
        - sum(wrapped.staging.cache_credits)
        + 3 * layer_bytes
    )
    monkeypatch.setattr(
        offload,
        "read_gpu_memory",
        lambda: GpuMemory(Memory.from_gb(12), Memory.from_bytes(free)),
    )
    _forward(wrapped, [2], cache)
    assert wrapped.staging.cache_credits == [one_cache, one_cache]


def test_unknown_nonfresh_cache_pool_is_rejected(cpu_staging: None) -> None:
    wrapped = _prepare(_model(), _policy())
    cache = [KVCache(), KVCache()]
    cache[0].offset = 1
    with pytest.raises(ValueError, match="fresh"):
        _forward(wrapped, [1], cache)


def test_partial_resident_initialization_failure_releases_owned_device_refs(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _model()
    embedding = cast(offload._QwenModel, cast(object, model)).model.embed_tokens  # pyright: ignore[reportPrivateUsage]
    norm = cast(offload._QwenModel, cast(object, model)).model.norm  # pyright: ignore[reportPrivateUsage]
    original = offload._materialize_resident  # pyright: ignore[reportPrivateUsage]
    calls = 0

    def fail_second(component: nn.Module, stream: mx.Stream) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            component["weight"] = mx.array([99.0])
            raise RuntimeError("injected-resident-failure")
        original(component, stream)

    monkeypatch.setattr(offload, "_materialize_resident", fail_second)
    with pytest.raises(RuntimeError, match="injected-resident-failure"):
        _prepare(model, _policy())
    assert embedding.parameters() == {}
    assert norm.parameters() == {}


@pytest.mark.parametrize("invalid", ["dtype", "shape", "capacity", "offset", "alias"])
def test_invalid_canonical_cache_never_receives_credit(
    cpu_staging: None, invalid: str
) -> None:
    wrapped = _prepare(_model(), _policy())
    cache = [KVCache(), KVCache()]
    wrapped.staging.register_cache_pool(cache)
    keys = mx.zeros((1, 2, 256, 16), dtype=mx.float32)
    values = mx.zeros_like(keys)
    if invalid == "dtype":
        keys = keys.astype(mx.float16)
        values = values.astype(mx.float16)
    elif invalid == "shape":
        values = mx.zeros((1, 1, 256, 16))
    elif invalid == "capacity":
        keys = mx.zeros((1, 2, 288, 16))
        values = mx.zeros_like(keys)
    if invalid == "alias":
        values = keys
    cache[0].keys = keys
    cache[0].values = values
    cache[0].offset = 257 if invalid == "offset" else 1
    mx.eval(keys, values)
    with pytest.raises(ValueError, match="dtype|capacity"):
        wrapped.staging.record_cache_credit(0, cache[0])
    assert wrapped.staging.cache_credits == [0, 0]


def test_resident_weights_do_not_copy_per_token(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        offload,
        "read_gpu_memory",
        lambda: GpuMemory(Memory.from_gb(12), Memory.from_gb(10)),
    )
    wrapped = _prepare(_model(), _policy())
    cached = [KVCache(), KVCache()]
    copies = 0
    original_copy = type(wrapped.staging).copy_to_device

    def counted(staging: offload._LayerStaging, value: mx.array) -> mx.array:  # pyright: ignore[reportPrivateUsage]
        nonlocal copies
        copies += 1
        return original_copy(staging, value)

    monkeypatch.setattr(type(wrapped.staging), "copy_to_device", counted)
    for tokens in ([1, 2], [3], [4]):
        _forward(wrapped, tokens, cached)
    # One hidden tensor per layer, with the dense causal mask copied only in prefill.
    assert copies <= 8
    assert wrapped.stages_opened == wrapped.stages_closed == 0


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
    assert (
        wrapped.canonical_host_weight_bytes
        == needed - wrapped.persistent_gpu_weight_bytes
    )
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
    original_parameters = wrapped.overflow_host_parameters
    actual_cache = [KVCache(), KVCache()]
    for tokens, expected in zip(([1, 2, 3], [4], [5]), reference, strict=True):
        actual = _forward(wrapped, tokens, actual_cache)
        np.testing.assert_allclose(
            np.array(actual), np.array(expected), atol=1e-5, rtol=1e-5
        )
        assert wrapped.active_layer is None
        assert wrapped.overflow_host_parameters is original_parameters
    expected_stages = 3 * sum(
        layer.host_parameters is not None for layer in wrapped.staging.layers
    )
    assert wrapped.stages_opened == wrapped.stages_closed == expected_stages
    assert [entry.offset for entry in actual_cache] == [5, 5]
    for expected, actual in zip(reference_cache, actual_cache, strict=True):
        for a, b in zip(expected.state, actual.state, strict=True):
            np.testing.assert_allclose(np.array(a), np.array(b), atol=1e-5, rtol=1e-5)


@pytest.mark.parametrize("tie_word_embeddings", [False, True])
@pytest.mark.parametrize("group_size", [32, 64])
def test_bfloat16_wide_output_projection_matches_float32_dequantized_reference(
    cpu_staging: None, tie_word_embeddings: bool, group_size: int
) -> None:
    # Qwen3-32B's reduction width exposes scalar BF16 accumulation error that
    # the small-width staging tests cannot detect. Keep the vocabulary small.
    model = _model(
        1,
        tie_word_embeddings=tie_word_embeddings,
        dtype=mx.bfloat16,
        group_size=group_size,
        hidden_size=5120,
    )
    inner = cast(offload._QwenModel, cast(object, model)).model  # pyright: ignore[reportPrivateUsage]
    reference_cache = [KVCache()]
    hidden_states: list[mx.array] = []
    for tokens in ([1, 2, 3], [4]):
        hidden = cast(Callable[..., mx.array], inner)(
            mx.array([tokens]), cache=reference_cache
        )
        mx.eval(hidden, *reference_cache[0].state)
        hidden_states.append(hidden)
    projection = (
        inner.embed_tokens
        if tie_word_embeddings
        else cast(nn.Module, cast(dict[str, object], model)["lm_head"])
    )
    parameters = cast(dict[str, mx.array], projection.parameters())
    packed = np.array(parameters["weight"])
    scales = np.array(parameters["scales"].astype(mx.float32))
    biases = np.array(parameters["biases"].astype(mx.float32))
    unpacked = (
        (packed[:, :, None] >> np.arange(0, 32, 4, dtype=np.uint32)) & 15
    ).reshape(128, 5120)
    dequantized = unpacked.astype(np.float32) * np.repeat(
        scales, group_size, axis=1
    ) + np.repeat(biases, group_size, axis=1)
    wrapped = _prepare(model, replace(_policy(), stage_limit_bytes=2 * 1024**2))
    canonical = cast(dict[str, mx.array], projection.parameters())
    actual_cache = [KVCache()]
    for tokens, hidden in zip(([1, 2, 3], [4]), hidden_states, strict=True):
        expected = np.array(hidden.astype(mx.float32)) @ dequantized.T
        actual = _forward(wrapped, tokens, actual_cache)
        np.testing.assert_allclose(
            np.array(actual.astype(mx.float32)), expected, atol=1e-4, rtol=1e-4
        )
        assert actual.dtype == mx.float32
    assert reference_cache[0].offset == actual_cache[0].offset == 4
    assert (
        wrapped.stages_opened
        == wrapped.stages_closed
        == 2
        * sum(layer.host_parameters is not None for layer in wrapped.staging.layers)
    )
    after = cast(dict[str, mx.array], projection.parameters())
    assert after["weight"] is canonical["weight"]
    assert after["scales"] is canonical["scales"]
    assert after["biases"] is canonical["biases"]
    assert after["weight"].dtype == mx.uint32
    assert after["scales"].dtype == after["biases"].dtype == mx.bfloat16


def test_discarded_prefill_logits_are_not_eagerly_evaluated(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapped = _prepare(_model(tie_word_embeddings=False), _policy())
    original_eval = mx.eval

    def checked_eval(*values: "mx.MX_ARRAY_TREE | None") -> None:
        if wrapped.stages_closed == 2:
            assert not any(
                isinstance(value, mx.array) and value.shape == (1, 3, 128)
                for value in values
            ), "discarded prefill logits were evaluated eagerly"
        original_eval(*values)

    monkeypatch.setattr(mx, "eval", checked_eval)
    cache = [KVCache(), KVCache()]
    logits = wrapped(mx.array([[1, 2, 3]]), cache=cache)
    assert [entry.offset for entry in cache] == [3, 3]
    assert wrapped.stages_opened == wrapped.stages_closed == 2
    assert wrapped.active_layer is None
    original_eval(logits)
    assert logits.shape == (1, 3, 128)


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
        if layer.host_parameters is None:
            continue
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


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("EXO_TEST_WINDOWS_TEXT_OFFLOAD_GPU") != "1",
    reason="Explicit isolated GPU acceptance required",
)
def test_windows_gpu_bfloat16_untied_head_matches_cuda_reference() -> None:
    # Match the large dense Qwen3 checkpoint: BF16 outer/norm tensors and an
    # independent affine group64 quantized output head, not tied embedding logits.
    model = _model(tie_word_embeddings=False, dtype=mx.bfloat16, group_size=64)
    assert "lm_head" in model
    head = cast(nn.QuantizedLinear, model["lm_head"])
    assert cast(mx.array, head["scales"]).dtype == mx.bfloat16
    original = cast(offload._QwenModel, cast(object, model))  # pyright: ignore[reportPrivateUsage]
    norm = cast(nn.Module, cast(object, original.model.norm))
    assert cast(mx.array, norm["weight"]).dtype == mx.bfloat16
    reference_model = _model(
        tie_word_embeddings=False, dtype=mx.bfloat16, group_size=64
    )
    with mx.stream(mx.Device(mx.gpu)):
        reference_model.update(
            cast(
                dict[str, offload.ParameterTree],
                offload._map_parameters(  # pyright: ignore[reportPrivateUsage]
                    cast(offload.ParameterTree, model.parameters()),
                    lambda value: mx.add(value, mx.zeros_like(value)),
                ),
            )
        )
        mx.eval(reference_model.parameters())
        reference_cache = [KVCache(), KVCache()]
        reference = [
            _forward(reference_model, tokens, reference_cache)
            for tokens in ([1, 2, 3], [4], [5])
        ]
    wrapped = _prepare(model, _policy())
    actual_cache = [KVCache(), KVCache()]
    for tokens, expected in zip(([1, 2, 3], [4], [5]), reference, strict=True):
        actual = _forward(wrapped, tokens, actual_cache)
        np.testing.assert_allclose(
            np.array(actual.astype(mx.float32)),
            np.array(expected.astype(mx.float32)),
            atol=0.03,
            rtol=0.03,
        )
        assert wrapped.active_layer is None
    expected_stages = 3 * sum(
        layer.host_parameters is not None for layer in wrapped.staging.layers
    )
    assert wrapped.stages_opened == wrapped.stages_closed == expected_stages
    assert [entry.offset for entry in actual_cache] == [5, 5]
    for expected_cache, actual_entry in zip(reference_cache, actual_cache, strict=True):
        for expected_value, actual_value in zip(
            expected_cache.state, actual_entry.state, strict=True
        ):
            assert expected_value is not None and actual_value is not None
            np.testing.assert_allclose(
                np.array(actual_value.astype(mx.float32)),
                np.array(expected_value.astype(mx.float32)),
                atol=0.03,
                rtol=0.03,
            )


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
        if layer.host_parameters is None:
            continue
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
    expected_stages = 3 * sum(
        layer.host_parameters is not None for layer in wrapped.staging.layers
    )
    assert wrapped.stages_opened == wrapped.stages_closed == expected_stages
    for expected, actual in zip(reference_cache, actual_cache, strict=True):
        for a, b in zip(expected.state, actual.state, strict=True):
            np.testing.assert_allclose(np.array(a), np.array(b), atol=0.02, rtol=0.01)
    _exercise_failure_and_recovery(wrapped, monkeypatch)


def test_duplicate_cache_owners_are_rejected(cpu_staging: None) -> None:
    wrapped = _prepare(_model(), _policy())
    shared = KVCache()
    with pytest.raises(ValueError, match="unique|duplicate"):
        wrapped.staging.register_cache_pool([shared, shared])
    assert wrapped.staging.cache_pool_ids is None
    assert wrapped.staging.cache_credits == [0, 0]


@pytest.mark.parametrize("fail", [False, True])
def test_private_cache_credit_is_cleared_before_forward_returns(
    cpu_staging: None, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    wrapped = _prepare(_model(), _policy())
    if fail:
        record = type(wrapped.staging).record_cache_credit

        def record_then_fail(
            staging: offload._LayerStaging,  # pyright: ignore[reportPrivateUsage]
            index: int,
            cache: KVCache | None,
        ) -> None:
            record(staging, index, cache)
            raise RuntimeError("injected-private-cache-failure")

        monkeypatch.setattr(
            type(wrapped.staging), "record_cache_credit", record_then_fail
        )
        with pytest.raises(RuntimeError, match="private-cache"):
            wrapped(mx.array([[1]]))
    else:
        result = wrapped(mx.array([[1]]))
        mx.eval(result)
    assert wrapped.staging.cache_pool_ids is None
    assert wrapped.staging.cache_credits == [0, 0]


def test_allocator_cache_lease_is_exclusive_and_restores_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limits: list[int] = []

    def set_limit(limit: int) -> int:
        limits.append(limit)
        return 123

    monkeypatch.setattr(mx, "set_cache_limit", set_limit)
    monkeypatch.setattr(mx, "clear_cache", lambda: limits.append(-1))
    lease = offload._CudaCacheLease.acquire()  # pyright: ignore[reportPrivateUsage]
    assert limits == [0, -1]
    with pytest.raises(RuntimeError, match="exclusive"):
        offload._CudaCacheLease.acquire()  # pyright: ignore[reportPrivateUsage]
    lease.release()
    lease.release()
    assert limits == [0, -1, 123]


def test_residency_owns_cache_lease_until_model_close(
    cpu_staging: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[int] = []

    def set_limit(limit: int) -> int:
        events.append(limit)
        return 123

    monkeypatch.setattr(mx, "set_cache_limit", set_limit)
    monkeypatch.setattr(mx, "clear_cache", lambda: events.append(-1))
    wrapped = _prepare(_model(), _policy())
    assert events[0:2] == [0, -1]
    result = wrapped(mx.array([[1]]))
    mx.eval(result)
    wrapped.settle_request()
    assert 123 not in events
    wrapped.close()
    assert events[-2:] == [-1, 123]
    assert wrapped.original.parameters() == {}
    assert wrapped.staging.layers == ()
    wrapped.close()
    assert events.count(123) == 1
    with pytest.raises(RuntimeError, match="closed"):
        wrapped(mx.array([[1]]))


def test_residency_initialization_failure_restores_allocator_limit(
    cpu_staging: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[int] = []

    def set_limit(limit: int) -> int:
        events.append(limit)
        return 123

    monkeypatch.setattr(mx, "set_cache_limit", set_limit)
    monkeypatch.setattr(mx, "clear_cache", lambda: events.append(-1))

    def fail(component: nn.Module, stream: mx.Stream) -> None:
        component["weight"] = mx.array([99.0])
        raise RuntimeError("allocation-failure")

    monkeypatch.setattr(offload, "_materialize_resident", fail)
    with pytest.raises(RuntimeError, match="allocation-failure"):
        _prepare(_model(), _policy())
    assert events[0:2] == [0, -1]
    assert events[-2:] == [-1, 123]


def test_wrapper_construction_failure_restores_allocator_limit(
    cpu_staging: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[int] = []

    def set_limit(limit: int) -> int:
        events.append(limit)
        return 123

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("wrapper-construction-failure")

    monkeypatch.setattr(mx, "set_cache_limit", set_limit)
    monkeypatch.setattr(offload, "WindowsQwen3OffloadModel", fail)
    with pytest.raises(RuntimeError, match="wrapper-construction"):
        _prepare(_model(), _policy())
    assert events == [0, 123]


def test_physical_headroom_keeps_logical_fit_from_filling_resident_prefix(
    cpu_staging: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _model(4)
    inner = cast(offload._QwenModel, cast(object, model)).model  # pyright: ignore[reportPrivateUsage]
    layer_bytes = offload.parameter_bytes(inner.layers[0])
    logical_free = (
        _overflow_capacity(model, _policy()) - 256 * 1024**2 + 2 * layer_bytes
    )
    monkeypatch.setattr(
        offload,
        "read_gpu_memory",
        lambda: GpuMemory(
            Memory.from_gb(12), Memory.from_bytes(256 * 1024**2 + logical_free)
        ),
    )
    wrapped = _prepare(model, _policy())
    assert wrapped.residency_plan.resident_component_ids == (
        "head",
        "norm",
        "layer0",
        "layer1",
    )
    assert wrapped.residency_plan.overflow_component_ids == ("layer2", "layer3")
    assert wrapped.residency_plan.reserve_bytes == (
        _policy().gpu_reserve_bytes
        + wrapped.staging.kv_bytes
        + wrapped.staging.kv_scratch_bytes
    )
    monkeypatch.setattr(
        offload,
        "read_gpu_memory",
        lambda: GpuMemory(
            Memory.from_gb(12),
            Memory.from_bytes(wrapped.residency_plan.reserve_bytes - 1),
        ),
    )
    with pytest.raises(MemoryError, match="remaining dedicated"):
        wrapped(mx.array([[1]]))


@pytest.mark.parametrize("reclaimed_free", [50, 49, None])
def test_capacity_shortfall_reclaims_once_and_rechecks_actual_free(
    monkeypatch: pytest.MonkeyPatch, reclaimed_free: int | None
) -> None:
    samples = iter([49, reclaimed_free])
    events: list[str] = []
    def read() -> GpuMemory | None:
        events.append("read")
        value = next(samples)
        return None if value is None else GpuMemory(Memory.from_gb(12), Memory.from_bytes(value))
    monkeypatch.setattr(offload, "read_gpu_memory", read)
    monkeypatch.setattr(mx, "clear_cache", lambda: events.append("trim"))
    if reclaimed_free == 50:
        offload._check_gpu_capacity(10, _policy(), 20)  # pyright: ignore[reportPrivateUsage]
    else:
        with pytest.raises(MemoryError):
            offload._check_gpu_capacity(10, _policy(), 20)  # pyright: ignore[reportPrivateUsage]
    assert events == ["read", "trim", "read"]


@pytest.mark.parametrize("free", [50, None])
def test_capacity_fit_or_missing_nvml_does_not_trim(
    monkeypatch: pytest.MonkeyPatch, free: int | None
) -> None:
    events: list[str] = []
    def read() -> GpuMemory | None:
        events.append("read")
        return None if free is None else GpuMemory(Memory.from_gb(12), Memory.from_bytes(free))
    monkeypatch.setattr(offload, "read_gpu_memory", read)
    monkeypatch.setattr(mx, "clear_cache", lambda: events.append("trim"))
    if free is None:
        with pytest.raises(MemoryError):
            offload._check_gpu_capacity(10, _policy(), 20)  # pyright: ignore[reportPrivateUsage]
    else:
        offload._check_gpu_capacity(10, _policy(), 20)  # pyright: ignore[reportPrivateUsage]
    assert events == ["read"]