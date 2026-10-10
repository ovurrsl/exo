"""Opt-in, experimental dense Qwen3 staging with separate host/GPU budgets."""

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import ClassVar, Protocol, Self, cast, final

import mlx.core as mx
import mlx.nn as nn
import numpy as np
import psutil
from mlx_lm.models.cache import KVCache, QuantizedKVCache
from mlx_lm.models.qwen3 import Model as Qwen3Model
from mlx_lm.models.qwen3 import ModelArgs, TransformerBlock

from exo.utils.windows_gpu import read_gpu_memory
from exo.utils.windows_residency import (
    BudgetPolicy,
    CapacitySnapshot,
    ComponentSpec,
    ResidencyPlan,
    plan_residency,
    validate_stage_capacity,
)
from exo.utils.windows_text_offload_config import (
    WindowsTextOffloadPolicy as WindowsTextOffloadPolicy,
)
from exo.utils.windows_weights import parameter_bytes
from exo.worker.engines.mlx.types import KVCacheType

type ParameterTree = mx.array | list[ParameterTree] | dict[str, ParameterTree]
type AttentionMask = mx.array | str | None

# Planning-only slack for physical CUDA allocation overhead. The RTX 5070
# acceptance probe measured ~39 MB beyond parameter bytes and a ~28 MB stage
# deficit at an otherwise logical fit. This bounded allowance is not a universal
# driver guarantee; every stage still checks actual free VRAM. Do not also add it
# to the remaining reserve, which would consume the slack a second time.
_PHYSICAL_GPU_HEADROOM_BYTES = 256 * 1024**2


class _CudaCacheLease:
    """Exclusive process allocator ownership for a dedicated offload runner.

    CUDA's free-buffer cache can return pinned CPU buffers to GPU operations.
    Disable reuse throughout the model lifetime, including lazy output graphs.
    """

    _lock: ClassVar[Lock] = Lock()
    _active: ClassVar[bool] = False

    def __init__(self, previous_limit: int):
        self.previous_limit = previous_limit
        self.released = False

    @classmethod
    def acquire(cls) -> Self:
        with cls._lock:
            if cls._active:
                raise RuntimeError(
                    "CUDA offload requires exclusive allocator ownership"
                )
            previous = mx.set_cache_limit(0)
            try:
                # Setting the limit alone leaves existing pinned entries reusable.
                mx.clear_cache()
            except BaseException:
                mx.set_cache_limit(previous)
                raise
            cls._active = True
            return cls(previous)

    def release(self) -> None:
        with self._lock:
            if not self.released:
                mx.set_cache_limit(self.previous_limit)
                self.released = True
                type(self)._active = False


class _ParameterModule(Protocol):
    def parameters(self) -> dict[str, ParameterTree]: ...
    def update(self, parameters: dict[str, ParameterTree]) -> object: ...


class _Decoder(_ParameterModule, Protocol):
    def __call__(
        self,
        hidden: mx.array,
        mask: AttentionMask = None,
        cache: KVCache | QuantizedKVCache | None = None,
    ) -> mx.array: ...


class _InnerModel(Protocol):
    layers: list[nn.Module]
    embed_tokens: nn.Module
    norm: nn.Module

    def __call__(
        self, inputs: mx.array, cache: KVCacheType | None = None
    ) -> mx.array: ...


class _QwenModel(_ParameterModule, Protocol):
    model: _InnerModel
    args: object

    def __call__(
        self, inputs: mx.array, cache: KVCacheType | None = None
    ) -> mx.array: ...


class _Quantization(Protocol):
    mode: str
    bits: int
    group_size: int


class _EmbeddingProjection(Protocol):
    def as_linear(self, hidden: mx.array) -> mx.array: ...


def _cpu_output_projection(
    hidden: mx.array, projection: nn.Module, *, tied: bool
) -> mx.array:
    if isinstance(projection, (nn.QuantizedLinear, nn.QuantizedEmbedding)):
        quantization = cast(_Quantization, cast(object, projection))
        parameters = cast(dict[str, mx.array], projection.parameters())
        biases = parameters.get("biases")
        # Windows' scalar CPU QMM accumulates in its input dtype. A BF16
        # reduction over Qwen3-32B's 5120 features changes the token ranking.
        # Promote this operation while retaining canonical packed/BF16 weights.
        logits = mx.quantized_matmul(
            hidden.astype(mx.float32),
            parameters["weight"],
            scales=parameters["scales"].astype(mx.float32),
            biases=biases.astype(mx.float32) if biases is not None else None,
            transpose=True,
            group_size=quantization.group_size,
            bits=quantization.bits,
            mode=quantization.mode,
        )
        bias = parameters.get("bias")
        return logits + bias.astype(mx.float32) if bias is not None else logits
    if tied:
        return cast(_EmbeddingProjection, cast(object, projection)).as_linear(hidden)
    return cast(Callable[[mx.array], mx.array], projection)(hidden)


def _modules(value: object) -> Iterator[nn.Module]:
    if isinstance(value, nn.Module):
        yield value
        for child in cast(dict[str, object], value).values():
            yield from _modules(child)
    elif isinstance(value, dict):
        for child in cast(dict[str, object], value).values():
            yield from _modules(child)
    elif isinstance(value, list):
        for child in cast(list[object], value):
            yield from _modules(child)


def _map_parameters(
    tree: ParameterTree, copy: Callable[[mx.array], mx.array]
) -> ParameterTree:
    if isinstance(tree, mx.array):
        return copy(tree)
    if isinstance(tree, list):
        return [_map_parameters(value, copy) for value in tree]
    return {name: _map_parameters(value, copy) for name, value in tree.items()}


def _arrays(tree: ParameterTree) -> Iterator[mx.array]:
    if isinstance(tree, mx.array):
        yield tree
    elif isinstance(tree, list):
        for value in tree:
            yield from _arrays(value)
    else:
        for value in tree.values():
            yield from _arrays(value)


def _host_copy(value: mx.array) -> mx.array:
    # NumPy cannot export bfloat16; float32 represents each value exactly.
    with mx.stream(mx.Device(mx.cpu)):
        source = value.astype(mx.float32) if value.dtype == mx.bfloat16 else value
        result = mx.array(np.array(source), dtype=value.dtype)
        mx.eval(result)
        return result


def _host_available_bytes() -> int:
    return int(psutil.virtual_memory().available)


def _new_gpu_stream() -> mx.Stream:
    return mx.new_stream(mx.Device(mx.gpu))


def _state_arrays(state: object) -> Iterator[mx.array]:
    if isinstance(state, mx.array):
        yield state
    elif isinstance(state, (list, tuple)):
        for value in cast(list[object] | tuple[object, ...], state):
            yield from _state_arrays(value)


@final
@dataclass(frozen=True)
class _Layer:
    module: _Decoder
    host_parameters: dict[str, ParameterTree] | None
    bytes: int


@final
class _LayerStaging:
    def __init__(
        self,
        layers: list[nn.Module],
        policy: WindowsTextOffloadPolicy,
        stream: mx.Stream,
        plan: ResidencyPlan,
        kv_bytes: int,
        kv_scratch_bytes: int,
        kv_heads: int,
        head_dim: int,
        cache_dtype: mx.Dtype,
    ):
        self.policy = policy
        self.stream = stream
        self.plan = plan
        self.kv_bytes = kv_bytes
        self.kv_scratch_bytes = kv_scratch_bytes
        self.kv_heads = kv_heads
        self.head_dim = head_dim
        self.cache_dtype = cache_dtype
        self.cache_credits = [0] * len(layers)
        self.cache_pool_ids: tuple[int, ...] | None = None
        self.layers = tuple(
            _Layer(
                cast(_Decoder, cast(object, layer)),
                cast(dict[str, ParameterTree], layer.parameters())
                if f"layer{index}" in plan.overflow_component_ids
                else None,
                parameter_bytes(layer),
            )
            for index, layer in enumerate(layers)
        )
        self.active_layer: int | None = None
        self.stages_opened = 0
        self.stages_closed = 0
        self.peak_staged_weight_bytes = 0

    def remaining_reserve(self) -> int:
        return (
            self.policy.gpu_reserve_bytes
            + self.kv_scratch_bytes
            + max(0, self.kv_bytes - sum(self.cache_credits))
        )

    def register_cache_pool(self, cache: KVCacheType) -> None:
        identifiers = tuple(id(entry) for entry in cache)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Residency requires unique cache owners per layer")
        if identifiers != self.cache_pool_ids:
            if any(
                type(entry) is not KVCache
                or entry.offset != 0
                or entry.keys is not None
                or entry.values is not None
                for entry in cache
            ):
                raise ValueError(
                    "Residency requires a fresh single-owner plain KV cache pool"
                )
            self.cache_pool_ids = identifiers
            self.cache_credits = [0] * len(self.layers)

    def clear_cache_credit(self) -> None:
        self.cache_pool_ids = None
        self.cache_credits = [0] * len(self.layers)

    def record_cache_credit(self, index: int, cache: KVCache | None) -> None:
        if cache is None:
            return
        if (
            type(cache) is not KVCache
            or self.cache_pool_ids is None
            or id(cache) != self.cache_pool_ids[index]
        ):
            raise ValueError("KV credit requires the registered plain cache owner")
        keys, values = cache.keys, cache.values
        if keys is None and values is None and cache.offset == 0:
            return
        if (
            keys is None
            or values is None
            or keys is values
            or keys.shape != values.shape
            or keys.ndim != 4
            or keys.shape[0] != 1
            or keys.shape[1] != self.kv_heads
            or keys.shape[3] != self.head_dim
            or keys.dtype != self.cache_dtype
            or values.dtype != self.cache_dtype
            or not (
                0
                <= cache.offset
                <= keys.shape[2]
                <= self.policy.max_context_tokens + 255
            )
        ):
            raise ValueError(
                "KV capacity, dimensions or dtype exceed the residency plan"
            )
        self.cache_credits[index] = keys.nbytes + values.nbytes

    def copy_to_device(self, value: mx.array) -> mx.array:
        zeros = mx.zeros_like(value, stream=self.stream)
        # array(existing) aliases storage; arithmetic creates device outputs.
        result = (
            mx.logical_or(value, zeros, stream=self.stream)
            if value.dtype == mx.bool_
            else mx.add(value, zeros, stream=self.stream)
        )
        mx.eval(result)
        return result

    @contextmanager
    def stage(self, index: int) -> Iterator[_Decoder]:
        if self.active_layer is not None:
            raise RuntimeError("Nested or concurrent Qwen3 staging is unsupported")
        layer = self.layers[index]
        _check_gpu_capacity(
            layer.bytes if layer.host_parameters is not None else 0,
            self.policy,
            self.remaining_reserve(),
        )
        if layer.host_parameters is None:
            self.active_layer = index
            try:
                with mx.stream(self.stream):
                    yield layer.module
            finally:
                try:
                    mx.synchronize(self.stream)
                finally:
                    self.active_layer = None
            return
        device_parameters: ParameterTree | None = None
        counted = False
        try:
            with mx.stream(self.stream):
                device_parameters = _map_parameters(
                    layer.host_parameters, self.copy_to_device
                )
                mx.eval(*_arrays(device_parameters))
                _ = layer.module.update(
                    cast(dict[str, ParameterTree], device_parameters)
                )
                self.active_layer = index
                self.stages_opened += 1
                counted = True
                self.peak_staged_weight_bytes = max(
                    self.peak_staged_weight_bytes, layer.bytes
                )
                yield layer.module
        finally:
            # Complete every submitted operation before dropping its weight refs,
            # including partially copied trees and failed decoder evaluation.
            try:
                mx.synchronize(self.stream)
            finally:
                try:
                    _ = layer.module.update(layer.host_parameters)
                finally:
                    self.active_layer = None
                    if counted:
                        self.stages_closed += 1
                    device_parameters = None
                    mx.clear_cache()


@final
class _StagedQwen3Layer(nn.Module):
    def __init__(self, staging: _LayerStaging, index: int):
        super().__init__()
        self.original = cast(nn.Module, cast(object, staging.layers[index].module))
        self.staging = staging
        self.index = index

    def __call__(
        self,
        hidden: mx.array,
        mask: AttentionMask = None,
        cache: KVCache | QuantizedKVCache | None = None,
    ) -> mx.array:
        with self.staging.stage(self.index) as decoder:
            # Prior canonical KV stays credited through the live-free preflight.
            # Mutation invalidates that credit until evaluation and synchronization.
            self.staging.cache_credits[self.index] = 0
            device_hidden = self.staging.copy_to_device(hidden)
            device_mask = (
                self.staging.copy_to_device(mask)
                if isinstance(mask, mx.array)
                else mask
            )
            result = decoder(device_hidden, device_mask, cache)
            plain_cache = cast(KVCache | None, cache)
            cache_arrays = (
                ()
                if plain_cache is None
                else tuple(
                    value
                    for value in (plain_cache.keys, plain_cache.values)
                    if value is not None
                )
            )
            mx.eval(result, *cache_arrays)
            mx.synchronize(self.staging.stream)
            self.staging.record_cache_credit(self.index, plain_cache)
            return result


def _check_gpu_capacity(
    layer_bytes: int,
    policy: WindowsTextOffloadPolicy,
    reserve_bytes: int | None = None,
    *,
    enforce_stage_limit: bool = True,
) -> None:
    gpu = read_gpu_memory()
    if enforce_stage_limit and layer_bytes > policy.stage_limit_bytes:
        raise MemoryError("Qwen3 decoder layer exceeds the GPU stage limit")
    # Include copy temporaries, independently of MLX's pinned-host counters.
    if gpu is None:
        raise MemoryError("Insufficient dedicated NVIDIA VRAM for Qwen3 staging")
    validate_stage_capacity(
        free_gpu_bytes=gpu.free.in_bytes,
        layer_bytes=layer_bytes,
        reserve_bytes=policy.gpu_reserve_bytes
        if reserve_bytes is None
        else reserve_bytes,
    )


@final
class _ResidentUnary(nn.Module):
    def __init__(self, original: nn.Module, stream: mx.Stream):
        super().__init__()
        self.original = original
        self.stream = stream

    def __call__(self, inputs: mx.array) -> mx.array:
        with mx.stream(self.stream):
            return cast(Callable[[mx.array], mx.array], self.original)(inputs)


@final
class WindowsQwen3OffloadModel(nn.Module):
    def __init__(
        self,
        original: nn.Module,
        staging: _LayerStaging,
        overflow_host_parameters: dict[str, ParameterTree],
        projection: nn.Module,
        cache_lease: _CudaCacheLease,
    ):
        super().__init__()
        self.original = original
        self.staging = staging
        self.overflow_host_parameters = overflow_host_parameters
        self.projection = projection
        self.residency_plan = staging.plan
        self.cache_lease = cache_lease
        self.closed = False

    @property
    def model(self) -> nn.Module:
        return cast(
            nn.Module, cast(object, cast(_QwenModel, cast(object, self.original)).model)
        )

    @property
    def args(self) -> object:
        return cast(_QwenModel, cast(object, self.original)).args

    @property
    def model_type(self) -> str:
        return "qwen3"

    @property
    def canonical_host_weight_bytes(self) -> int:
        return sum(
            {
                id(value): value.nbytes
                for value in _arrays(self.overflow_host_parameters)
            }.values()
        )

    @property
    def persistent_gpu_weight_bytes(self) -> int:
        return self.residency_plan.persistent_gpu_bytes

    def settle_request(self) -> None:
        mx.synchronize(self.staging.stream)
        mx.synchronize(mx.default_stream(mx.Device(mx.cpu)))
        self.staging.clear_cache_credit()

    def close(self) -> None:
        """Release allocator ownership after generation and lazy outputs are settled.

        Direct callers must evaluate or discard outstanding output arrays first:
        stream synchronization cannot schedule an unevaluated external graph.
        The runner closes generation iterators and settles their streams first.
        """
        if self.closed:
            return
        self.settle_request()
        for layer in self.staging.layers:
            cast(nn.Module, cast(object, layer.module)).clear()
        self.staging.layers = ()
        self.overflow_host_parameters.clear()
        self.original.clear()
        self.projection.clear()
        mx.clear_cache()
        self.cache_lease.release()
        self.closed = True

    @property
    def layers(self) -> list[nn.Module]:
        return cast(_QwenModel, cast(object, self.original)).model.layers

    @property
    def active_layer(self) -> int | None:
        return self.staging.active_layer

    @property
    def stages_opened(self) -> int:
        return self.staging.stages_opened

    @property
    def stages_closed(self) -> int:
        return self.staging.stages_closed

    @property
    def peak_staged_weight_bytes(self) -> int:
        return self.staging.peak_staged_weight_bytes

    def __call__(
        self,
        inputs: mx.array,
        cache: KVCacheType | None = None,
        input_embeddings: mx.array | None = None,
    ) -> mx.array:
        if self.closed:
            raise RuntimeError("Qwen3 offload model is closed")
        policy = self.staging.policy
        if inputs.ndim != 2 or inputs.shape[0] != 1:
            raise ValueError("Experimental Qwen3 offload supports batch size one")
        if input_embeddings is not None:
            raise ValueError("Vision/input embeddings are unsupported by Qwen3 offload")
        if inputs.shape[1] > policy.max_prefill_tokens:
            raise ValueError("Qwen3 offload prefill chunk exceeds its bounded limit")
        if cache is not None and (
            len(cache) != len(self.layers)
            or any(type(entry) is not KVCache for entry in cache)
        ):
            raise ValueError(
                "Only single-owner dense Qwen3 unquantized KV caches are supported"
            )
        offset = max((entry.offset for entry in cache or []), default=0)
        if offset + inputs.shape[1] > policy.max_context_tokens:
            raise ValueError("Qwen3 offload context exceeds its bounded limit")
        private_cache = cache is None
        if private_cache:
            cache = [KVCache() for _ in self.layers]
        assert cache is not None
        try:
            self.staging.register_cache_pool(cache)
            # Only an overflowing untied embedding executes on CPU. Resident unary
            # modules and all decoder wrappers enter the explicitly owned GPU stream.
            with mx.stream(mx.Device(mx.cpu)):
                original = cast(_QwenModel, cast(object, self.original))
                hidden = original.model(inputs, cache=cache)
                tied = "lm_head" not in self.original
            with mx.stream(self.staging.stream):
                logits = _cpu_output_projection(hidden, self.projection, tied=tied)
            # MLX discards intermediate prefill logits. Decoder/cache evaluation is
            # already complete; keep the resident GPU head lazy so
            # discarded results do not evaluate a vocabulary-sized projection.
            with mx.stream(self.staging.stream):
                return mx.add(
                    logits,
                    mx.zeros_like(logits, stream=self.staging.stream),
                    stream=self.staging.stream,
                )

        finally:
            if private_cache:
                # Settle while the private canonical KV owners are still alive.
                self.settle_request()


def prepare_windows_qwen3_offload(
    model: nn.Module,
    policy: WindowsTextOffloadPolicy,
    *,
    world_size: int = 1,
    vision: bool = False,
    cpu_loaded: bool = False,
) -> WindowsQwen3OffloadModel:
    policy.validate()
    if sys.platform != "win32" or not mx.cuda.is_available():
        raise ValueError("Qwen3 RAM offload requires Windows CUDA")
    if world_size != 1 or vision:
        raise ValueError("Only single-node text inference without vision is supported")
    if not isinstance(model, Qwen3Model):
        raise ValueError("Only the standard dense Qwen3 architecture is supported")
    if not cpu_loaded:
        raise ValueError("Offload preparation requires the trusted CPU-stream loader")
    original = cast(_QwenModel, cast(object, model))
    if not original.model.layers:
        raise ValueError("Qwen3 must contain decoder layers")
    if any(not isinstance(layer, TransformerBlock) for layer in original.model.layers):
        raise ValueError("Only original dense Qwen3 decoder layers are supported")
    for component in _modules(model):
        if isinstance(component, (nn.QuantizedLinear, nn.QuantizedEmbedding)):
            quantization = cast(_Quantization, cast(object, component))
            if (
                quantization.mode != "affine"
                or quantization.bits != 4
                or quantization.group_size not in (32, 64)
            ):
                raise ValueError(
                    "CPU Qwen3 heads require affine 4-bit group32/group64 quantization"
                )
    tied = "lm_head" not in model
    projection = (
        original.model.embed_tokens if tied else cast(nn.Module, model["lm_head"])
    )
    components: dict[str, nn.Module] = {
        "head": projection,
        "norm": original.model.norm,
        **{f"layer{index}": layer for index, layer in enumerate(original.model.layers)},
    }
    if not tied:
        components["embedding"] = original.model.embed_tokens
    seen_arrays: set[int] = set()
    for component in components.values():
        identities = {
            id(value) for value in _arrays(cast(ParameterTree, component.parameters()))
        }
        if seen_arrays.intersection(identities):
            raise ValueError(
                "Partial aliases across Qwen3 ownership components are unsupported"
            )
        seen_arrays.update(identities)
    specifications = (
        ComponentSpec(
            "head",
            ("embedding",) if tied else (),
            frozenset({"head", "embedding"}) if tied else frozenset({"head"}),
            parameter_bytes(projection),
        ),
        ComponentSpec(
            "norm", (), frozenset({"norm"}), parameter_bytes(original.model.norm)
        ),
        *(
            ComponentSpec(
                f"layer{index}",
                (),
                frozenset({"decoder"}),
                parameter_bytes(layer),
                index,
            )
            for index, layer in enumerate(original.model.layers)
        ),
        *(
            (
                ComponentSpec(
                    "embedding",
                    (),
                    frozenset({"embedding"}),
                    parameter_bytes(original.model.embed_tokens),
                ),
            )
            if not tied
            else ()
        ),
    )
    args = cast(ModelArgs, original.args)
    dtype_bytes = _decoder_storage_width(original.model.layers)
    cache_dtype = next(
        value.dtype
        for value in _arrays(
            cast(ParameterTree, original.model.embed_tokens.parameters())
        )
        if mx.issubdtype(value.dtype, mx.floating)
    )
    if args.num_key_value_heads <= 0 or args.head_dim <= 0:
        raise ValueError("Invalid dense Qwen3 KV dimensions")
    layer_kv = (
        2
        * args.num_key_value_heads
        * args.head_dim
        * (policy.max_context_tokens + 255)
        * dtype_bytes
    )
    kv_bytes = layer_kv * len(original.model.layers)
    kv_scratch_bytes = 2 * layer_kv
    memory = read_gpu_memory()
    if memory is None:
        raise MemoryError(
            "NVIDIA VRAM capacity is unavailable before residency planning"
        )
    plan = plan_residency(
        specifications,
        CapacitySnapshot(
            max(0, memory.free.in_bytes - _PHYSICAL_GPU_HEADROOM_BYTES),
            _host_available_bytes(),
        ),
        BudgetPolicy(
            policy.gpu_reserve_bytes,
            kv_bytes,
            kv_scratch_bytes,
            policy.host_reserve_bytes,
            policy.host_limit_bytes,
            6 * max(spec.byte_size for spec in specifications),
        ),
    )
    if any(
        spec.byte_size > policy.stage_limit_bytes
        for spec in specifications
        if spec.component_id in plan.overflow_component_ids and "decoder" in spec.roles
    ):
        raise MemoryError("Qwen3 overflow decoder layer exceeds the GPU stage limit")
    stream = _new_gpu_stream()
    cache_lease = _CudaCacheLease.acquire()
    resident_modules: list[nn.Module] = []
    overflow_host_parameters: dict[str, ParameterTree] = {}
    try:
        for identifier in plan.resident_component_ids:
            component = components[identifier]
            _check_gpu_capacity(
                parameter_bytes(component),
                policy,
                plan.reserve_bytes,
                enforce_stage_limit=False,
            )
            resident_modules.append(component)
            _materialize_resident(component, stream)
        for identifier in plan.overflow_component_ids:
            component = components[identifier]
            with mx.stream(mx.Device(mx.cpu)):
                _canonicalize_component(component)
            overflow_host_parameters[identifier] = cast(
                ParameterTree, component.parameters()
            )
        staging = _LayerStaging(
            original.model.layers,
            policy,
            stream,
            plan,
            kv_bytes,
            kv_scratch_bytes,
            args.num_key_value_heads,
            args.head_dim,
            cache_dtype,
        )
        original.model.layers = [
            _StagedQwen3Layer(staging, index) for index in range(len(staging.layers))
        ]
        original.model.norm = _ResidentUnary(original.model.norm, stream)
        if tied or "embedding" in plan.resident_component_ids:
            original.model.embed_tokens = _ResidentUnary(
                original.model.embed_tokens, stream
            )
        return WindowsQwen3OffloadModel(
            model, staging, overflow_host_parameters, projection, cache_lease
        )
    except BaseException:
        mx.synchronize(stream)
        for component in resident_modules:
            component.clear()
        overflow_host_parameters.clear()
        mx.clear_cache()
        cache_lease.release()
        raise


def _decoder_storage_width(layers: list[nn.Module]) -> int:
    width = 0
    for layer in layers:
        for value in _arrays(cast(ParameterTree, layer.parameters())):
            if mx.issubdtype(value.dtype, mx.floating):
                if value.dtype not in (mx.float16, mx.bfloat16, mx.float32):
                    raise ValueError("Unsupported Qwen3 KV storage dtype")
                width = max(width, 4 if value.dtype == mx.float32 else 2)
    if not width:
        raise ValueError("Missing Qwen3 floating storage dtype")
    return width


def _materialize_resident(component: nn.Module, stream: mx.Stream) -> None:
    source = cast(ParameterTree, component.parameters())
    copied: dict[int, mx.array] = {}

    def copy_once(value: mx.array) -> mx.array:
        if id(value) not in copied:
            with mx.stream(stream):
                result = mx.add(
                    value, mx.zeros_like(value, stream=stream), stream=stream
                )
                mx.eval(result)
                copied[id(value)] = result
        return copied[id(value)]

    try:
        with mx.stream(stream):
            parameters = cast(
                dict[str, ParameterTree], _map_parameters(source, copy_once)
            )
            mx.eval(*_arrays(parameters))
            mx.synchronize(stream)
            component.update(parameters)
    finally:
        mx.synchronize(stream)
        copied.clear()


def _canonicalize_component(component: nn.Module) -> None:
    module = cast(_ParameterModule, cast(object, component))
    source = module.parameters()
    copied: dict[int, mx.array] = {}

    def copy_once(value: mx.array) -> mx.array:
        # All source references stay alive until this component is replaced.
        # Reset the memo for every component: allocator/Python IDs may be reused
        # after old weights are released during incremental canonicalization.
        key = id(value)
        if key not in copied:
            copied[key] = _host_copy(value)
        return copied[key]

    parameters = cast(dict[str, ParameterTree], _map_parameters(source, copy_once))
    _ = module.update(parameters)
