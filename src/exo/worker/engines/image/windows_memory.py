"""Windows CUDA diffusion stages with canonical host copies of model weights."""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol, cast, final

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mflux.models.common.vae.vae_tiler import VAETiler

from exo.shared.models.windows_image_budget import WINDOWS_IMAGE_CUDA_RESERVE
from exo.shared.types.memory import Memory
from exo.utils.windows_gpu import read_gpu_memory

type ParameterTree = mx.array | list[ParameterTree] | dict[str, ParameterTree]


class _ParameterModule(Protocol):
    def parameters(self) -> dict[str, ParameterTree]: ...
    def update(self, parameters: dict[str, ParameterTree]) -> object: ...


class _VaeDecoder(Protocol):
    decode: Callable[[mx.array], mx.array]
    encode: Callable[[mx.array], mx.array]


def _map_parameters(
    tree: ParameterTree, transform: Callable[[mx.array], mx.array]
) -> ParameterTree:
    if isinstance(tree, mx.array):
        return transform(tree)
    if isinstance(tree, list):
        return [_map_parameters(value, transform) for value in tree]
    return {name: _map_parameters(value, transform) for name, value in tree.items()}


def _parameter_arrays(tree: ParameterTree) -> Iterator[mx.array]:
    if isinstance(tree, mx.array):
        yield tree
    elif isinstance(tree, list):
        for value in tree:
            yield from _parameter_arrays(value)
    else:
        for value in tree.values():
            yield from _parameter_arrays(value)


def _host_copy(array: mx.array) -> mx.array:
    # bfloat16 has no NumPy buffer format. Float32 represents every bfloat16
    # value exactly, and conversion back preserves the original weight dtype.
    source = array.astype(mx.float32) if array.dtype == mx.bfloat16 else array
    return mx.array(np.array(source), dtype=array.dtype)


@final
@dataclass(frozen=True)
class _Component:
    module: _ParameterModule
    host_parameters: dict[str, ParameterTree]
    bytes: int


@final
class WindowsImageMemoryManager:
    """Only one phase's parameters occupy VRAM; inactive phases keep CPU refs."""

    def __init__(self, model: nn.Module, reserve: Memory = WINDOWS_IMAGE_CUDA_RESERVE):
        self._reserve = reserve
        self._components: dict[str, _Component] = {}
        self._active: tuple[str, ...] = ()
        self._require_cuda = False
        self._device = mx.Device(mx.cpu)
        with mx.stream(self._device):
            for name in (
                "transformer",
                "vae",
                "text_encoder",
                "t5_text_encoder",
                "clip_text_encoder",
            ):
                component: object = getattr(model, name, None)
                if not isinstance(component, nn.Module):
                    continue
                module = cast(_ParameterModule, cast(object, component))
                parameters = cast(
                    dict[str, ParameterTree],
                    _map_parameters(module.parameters(), _host_copy),
                )
                arrays = list(_parameter_arrays(parameters))
                mx.eval(*arrays)
                _ = module.update(parameters)
                self._components[name] = _Component(
                    module, parameters, sum(array.nbytes for array in arrays)
                )
        if "transformer" not in self._components or "vae" not in self._components:
            raise ValueError("Windows image staging requires a transformer and a VAE")
        self._install_vae_tiling(model)
        mx.clear_cache()

    @property
    def prompt_components(self) -> tuple[str, ...]:
        return tuple(
            name for name in self._components if name not in ("transformer", "vae")
        )

    @property
    def active_components(self) -> tuple[str, ...]:
        return self._active

    def _offload(self) -> None:
        for name in self._active:
            component = self._components[name]
            _ = component.module.update(component.host_parameters)
        self._active = ()
        mx.clear_cache()

    def _activate(self, names: tuple[str, ...], require_cuda: bool) -> mx.Device:
        required = sum(self._components[name].bytes for name in names)
        memory = read_gpu_memory()
        available = (
            max(0, memory.free.in_bytes - self._reserve.in_bytes)
            if memory is not None
            else 0
        )
        use_cuda = memory is not None and required <= available
        if require_cuda and not use_cuda:
            raise RuntimeError(
                f"The Windows diffusion shard needs {required} bytes of GPU weights; "
                f"only {available} bytes remain after the activation reserve"
            )
        device = mx.Device(mx.gpu if use_cuda else mx.cpu)
        if use_cuda:
            with mx.stream(device):
                for name in names:
                    component = self._components[name]
                    # array(existing) can alias CPU storage. An evaluated GPU
                    # add creates actual device buffers, including packed ints.
                    parameters = cast(
                        dict[str, ParameterTree],
                        _map_parameters(
                            component.host_parameters,
                            lambda value: mx.add(
                                value,
                                mx.zeros_like(value, stream=device),
                                stream=device,
                            ),
                        ),
                    )
                    mx.eval(*_parameter_arrays(parameters))
                    _ = component.module.update(parameters)
                    self._active = (*self._active, name)
        self._active = names
        self._require_cuda = require_cuda
        self._device = device
        return device

    @contextmanager
    def stage(
        self, names: Sequence[str], *, require_cuda: bool = False
    ) -> Iterator[mx.Device]:
        previous, previous_required = self._active, self._require_cuda
        completed = False
        self._offload()
        try:
            device = self._activate(tuple(names), require_cuda)
            with mx.stream(device):
                try:
                    yield device
                    completed = True
                finally:
                    mx.synchronize(mx.default_stream(device))
        finally:
            self._offload()
            if previous and completed:
                _ = self._activate(previous, previous_required)

    @staticmethod
    def _install_vae_tiling(model: nn.Module) -> None:
        vae: object = getattr(model, "vae", None)
        decoder = cast(_VaeDecoder, vae)
        decode, encode = decoder.decode, decoder.encode
        scale: object = getattr(vae, "spatial_scale", 8)
        channels: object = getattr(vae, "latent_channels", 16)
        if not isinstance(scale, int) or not isinstance(channels, int):
            raise ValueError("The VAE must declare integer spatial scale and channels")

        def tiled_decode(latents: mx.array) -> mx.array:
            if latents.ndim == 4:
                latents = latents[:, :, None, :, :]
            return VAETiler.decode_image_tiled(
                latent=latents,
                decode_fn=decode,
                spatial_scale=scale,
                tile_size=(512, 512),
                tile_overlap=(64, 64),
            )

        def tiled_encode(image: mx.array) -> mx.array:
            if image.ndim == 5:
                image = image[:, :, 0, :, :]
            return VAETiler.encode_image_tiled(
                image=image,
                encode_fn=encode,
                latent_channels=channels,
                spatial_scale=scale,
                tile_size=(512, 512),
                tile_overlap=(64, 64),
            )

        decoder.decode = tiled_decode
        decoder.encode = tiled_encode
