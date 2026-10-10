"""Opt-in, experimental dense Qwen3 staging with separate host/GPU budgets."""

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol, cast, final

import mlx.core as mx
import mlx.nn as nn
import numpy as np
import psutil
from mlx_lm.models.cache import KVCache, QuantizedKVCache
from mlx_lm.models.qwen3 import Model as Qwen3Model
from mlx_lm.models.qwen3 import TransformerBlock

from exo.utils.windows_gpu import read_gpu_memory
from exo.utils.windows_text_offload_config import (
    WindowsTextOffloadPolicy as WindowsTextOffloadPolicy,
)
from exo.utils.windows_weights import parameter_bytes
from exo.worker.engines.mlx.types import KVCacheType

type ParameterTree = mx.array | list[ParameterTree] | dict[str, ParameterTree]
type AttentionMask = mx.array | str | None


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
    host_parameters: dict[str, ParameterTree]
    bytes: int


@final
class _LayerStaging:
    def __init__(self, layers: list[nn.Module], policy: WindowsTextOffloadPolicy):
        self.policy = policy
        self.stream = _new_gpu_stream()
        self.layers = tuple(
            _Layer(
                cast(_Decoder, cast(object, layer)),
                cast(dict[str, ParameterTree], layer.parameters()),
                parameter_bytes(layer),
            )
            for layer in layers
        )
        self.active_layer: int | None = None
        self.stages_opened = 0
        self.stages_closed = 0
        self.peak_staged_weight_bytes = 0

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
        _check_gpu_capacity(layer.bytes, self.policy)
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
            device_hidden = self.staging.copy_to_device(hidden)
            device_mask = (
                self.staging.copy_to_device(mask)
                if isinstance(mask, mx.array)
                else mask
            )
            result = decoder(device_hidden, device_mask, cache)
            mx.eval(result, *(_state_arrays(cache.state) if cache is not None else ()))
            return result


def _check_gpu_capacity(layer_bytes: int, policy: WindowsTextOffloadPolicy) -> None:
    gpu = read_gpu_memory()
    if layer_bytes > policy.stage_limit_bytes:
        raise MemoryError("Qwen3 decoder layer exceeds the GPU stage limit")
    # Include copy temporaries, independently of MLX's pinned-host counters.
    if gpu is None or gpu.free.in_bytes < policy.gpu_reserve_bytes + 3 * layer_bytes:
        raise MemoryError("Insufficient dedicated NVIDIA VRAM for Qwen3 staging")


@final
class WindowsQwen3OffloadModel(nn.Module):
    def __init__(
        self,
        original: nn.Module,
        host_parameters: dict[str, ParameterTree],
        staging: _LayerStaging,
    ):
        super().__init__()
        self.original = original
        self.host_parameters = host_parameters
        self.staging = staging

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
                id(value): value.nbytes for value in _arrays(self.host_parameters)
            }.values()
        )

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
        policy = self.staging.policy
        if inputs.ndim != 2 or inputs.shape[0] != 1:
            raise ValueError("Experimental Qwen3 offload supports batch size one")
        if input_embeddings is not None:
            raise ValueError("Vision/input embeddings are unsupported by Qwen3 offload")
        if inputs.shape[1] > policy.max_prefill_tokens:
            raise ValueError("Qwen3 offload prefill chunk exceeds its bounded limit")
        if cache is not None and (
            len(cache) != len(self.layers)
            or any(
                not isinstance(entry, (KVCache, QuantizedKVCache)) for entry in cache
            )
        ):
            raise ValueError("Only dense Qwen3 KV caches are supported")
        offset = max((entry.offset for entry in cache or []), default=0)
        if offset + inputs.shape[1] > policy.max_context_tokens:
            raise ValueError("Qwen3 offload context exceeds its bounded limit")
        # The real Qwen3 forward runs CPU embedding, final norm and its tied or
        # untied head. Only the replacement decoder layers enter the GPU stream.
        with mx.stream(mx.Device(mx.cpu)):
            original = cast(_QwenModel, cast(object, self.original))
            hidden = original.model(inputs, cache=cache)
            tied = "lm_head" not in self.original
            projection = (
                original.model.embed_tokens
                if tied
                else cast(nn.Module, cast(dict[str, object], self.original)["lm_head"])
            )
            logits = _cpu_output_projection(hidden, projection, tied=tied)
        # MLX discards intermediate prefill logits. Decoder/cache evaluation is
        # already complete; keep the canonical CPU head and final copy lazy so
        # discarded results do not evaluate a vocabulary-sized projection.
        with mx.stream(self.staging.stream):
            return mx.add(
                logits,
                mx.zeros_like(logits, stream=self.staging.stream),
                stream=self.staging.stream,
            )


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
    needed = parameter_bytes(model)
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
    components = [
        original.model.embed_tokens,
        original.model.norm,
        *original.model.layers,
    ]
    if "lm_head" in model:
        components.append(cast(nn.Module, cast(dict[str, object], model)["lm_head"]))
    largest_component = max(parameter_bytes(component) for component in components)
    if (
        needed > policy.host_limit_bytes
        or needed + 6 * largest_component + policy.host_reserve_bytes
        > _host_available_bytes()
    ):
        raise MemoryError("Insufficient host RAM or explicit host weight budget")
    _check_gpu_capacity(
        max(parameter_bytes(layer) for layer in original.model.layers), policy
    )
    with mx.stream(mx.Device(mx.cpu)):
        # Finish and replace one component before loading the next. The trusted
        # loader creates lazy CPU Load primitives, so a second full model copy
        # never accumulates. Tied embeddings are a single component.
        for component in components:
            _canonicalize_component(component)
        host_parameters = original.parameters()
    staging = _LayerStaging(original.model.layers, policy)
    original.model.layers = [
        _StagedQwen3Layer(staging, index) for index in range(len(staging.layers))
    ]
    return WindowsQwen3OffloadModel(model, host_parameters, staging)


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
