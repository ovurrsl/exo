import weakref
from typing import Protocol, cast
from unittest import mock

import mlx.core as mx
import mlx.nn as nn
import pytest
from mflux.models.flux.model.flux_text_encoder.clip_encoder.clip_mlp import CLIPMLP
from mflux.models.flux.model.flux_transformer.ada_layer_norm_continuous import (
    AdaLayerNormContinuous,
)
from mflux.models.flux.model.flux_vae.common.resnet_block_2d import ResnetBlock2D

from exo.shared.types.memory import Memory
from exo.utils.windows_gpu import GpuMemory
from exo.worker.engines.image.models.flux.wrappers import (
    FluxNormGateState,
    FluxSingleBlockWrapper,
)
from exo.worker.engines.image.pipeline.kv_cache import ImagePatchKVCache
from exo.worker.engines.image.pipeline.runner import DiffusionRunner
from exo.worker.engines.image.windows_memory import WindowsImageMemoryManager


class SmallVae(nn.Module):
    spatial_scale = 1
    latent_channels = 32

    def __init__(self) -> None:
        super().__init__()
        self.block = ResnetBlock2D(32, 32, 32, 32, 32, 32)

    def decode(self, latents: mx.array) -> mx.array:
        return self.block(latents[:, :, 0, :, :])[:, :, None, :, :]

    def encode(self, image: mx.array) -> mx.array:
        return self.decode(image)


class SmallImageModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.transformer = AdaLayerNormContinuous(8, 8)
        self.clip_text_encoder = CLIPMLP()
        self.vae = SmallVae()


class _LinearParameters(Protocol):
    weight: mx.array


class _NormParameters(Protocol):
    linear: _LinearParameters


class _RetainedWrapper(FluxSingleBlockWrapper):
    def __init__(self) -> None:
        self._kv_cache = ImagePatchKVCache(1, 1, 2, 8)
        self._norm_state = FluxNormGateState(
            norm_hidden=mx.ones((1, 2, 8)), gate=mx.ones((1, 8))
        )


class _StepStateRunner(DiffusionRunner):
    def __init__(
        self,
        manager: WindowsImageMemoryManager | None,
        world_size: int,
        wrapper: FluxSingleBlockWrapper,
    ) -> None:
        self._windows_memory = manager
        self.pipeline_world_size = world_size
        self.joint_block_wrappers = None
        self.single_block_wrappers = [wrapper]
        self._wrappers_initialized = True
        self._current_text_seq_len = 512

    def release_step(self) -> None:
        self._release_windows_step_state()

    @property
    def has_wrappers(self) -> bool:
        return self._wrappers_initialized


def _transformer_weight(model: SmallImageModel) -> mx.array:
    return cast(_NormParameters, cast(object, model.transformer)).linear.weight


def _capacity(free_mb: int) -> GpuMemory:
    return GpuMemory(total=Memory.from_mb(12 * 1024), free=Memory.from_mb(free_mb))


def test_real_mflux_components_stage_on_cuda_and_restore_host_weights():
    if not mx.cuda.is_available():
        pytest.skip("Requires a real MLX CUDA device")
    with mx.stream(mx.Device(mx.cpu)):
        model = SmallImageModel()
        manager = WindowsImageMemoryManager(model)
        embeddings = mx.ones((1, 2, 768))
        latents = mx.ones((1, 2, 8))
        conditioning = mx.ones((1, 8))
        vae_latents = mx.ones((1, 32, 1, 8, 8))
        expected_text = model.clip_text_encoder(embeddings)
        expected_transformer = model.transformer(latents, conditioning)
        expected_vae = model.vae.decode(vae_latents)
        mx.eval(expected_text, expected_transformer, expected_vae)
    original_weight = _transformer_weight(model)
    with mock.patch(
        "exo.worker.engines.image.windows_memory.read_gpu_memory",
        return_value=_capacity(8 * 1024),
    ):
        with manager.stage(manager.prompt_components) as device:
            assert device == mx.Device(mx.gpu)
            actual_text = model.clip_text_encoder(embeddings)
            mx.eval(actual_text)
        with manager.stage(("transformer",), require_cuda=True) as device:
            assert device == mx.Device(mx.gpu)
            assert _transformer_weight(model) is not original_weight
            actual_transformer = model.transformer(latents, conditioning)
            mx.eval(actual_transformer)
            with manager.stage(("vae",)):
                # Partial-image decode releases transformer GPU weights first.
                assert _transformer_weight(model) is original_weight
                actual_vae = model.vae.decode(vae_latents)
                mx.eval(actual_vae)
            assert _transformer_weight(model) is not original_weight
        assert _transformer_weight(model) is original_weight
    with mx.stream(mx.Device(mx.cpu)):
        assert mx.allclose(actual_text, expected_text, atol=0.02, rtol=0.02).item()
        assert mx.allclose(
            actual_transformer, expected_transformer, atol=0.02, rtol=0.02
        ).item()
        assert mx.allclose(actual_vae, expected_vae, atol=0.03, rtol=0.03).item()


def test_text_encoding_falls_back_to_cpu_and_transformer_fails_closed():
    with mx.stream(mx.Device(mx.cpu)):
        model = SmallImageModel()
        manager = WindowsImageMemoryManager(model)
    with mock.patch(
        "exo.worker.engines.image.windows_memory.read_gpu_memory", return_value=None
    ):
        with manager.stage(manager.prompt_components) as device:
            assert device == mx.Device(mx.cpu)
        with (
            pytest.raises(RuntimeError, match="activation reserve"),
            manager.stage(("transformer",), require_cuda=True),
        ):
            pass


def test_failed_stage_restores_cpu_parameters():
    if not mx.cuda.is_available():
        pytest.skip("Requires a real MLX CUDA device")
    with mx.stream(mx.Device(mx.cpu)):
        model = SmallImageModel()
        manager = WindowsImageMemoryManager(model)
    original_weight = _transformer_weight(model)
    with (
        mock.patch(
            "exo.worker.engines.image.windows_memory.read_gpu_memory",
            return_value=_capacity(8 * 1024),
        ),
        pytest.raises(ValueError, match="cancelled"),
        manager.stage(("transformer",), require_cuda=True),
    ):
        raise ValueError("cancelled")
    assert _transformer_weight(model) is original_weight


def test_failed_nested_decode_does_not_reactivate_previous_weights() -> None:
    with mx.stream(mx.Device(mx.cpu)):
        model = SmallImageModel()
        manager = WindowsImageMemoryManager(model)
    with (
        mock.patch(
            "exo.worker.engines.image.windows_memory.read_gpu_memory", return_value=None
        ),
        manager.stage(("transformer",)),
    ):
        with (
            pytest.raises(ValueError, match="decode failed"),
            manager.stage(("vae",)),
        ):
            raise ValueError("decode failed")
        assert manager.active_components == ()


@pytest.mark.parametrize("windows,world_size", [(True, 1), (True, 2), (False, 1)])
def test_completed_windows_single_node_step_releases_retained_tensor_states(
    windows: bool, world_size: int
) -> None:
    # Construct just the real wrapper's retained state, without allocating a
    # full 3072-dimensional FLUX block. These tensors/cache are real MLX objects.
    with mx.stream(mx.Device(mx.cpu)):
        wrapper = _RetainedWrapper()
        manager = WindowsImageMemoryManager(SmallImageModel()) if windows else None
    retained = weakref.ref(wrapper)
    runner = _StepStateRunner(manager, world_size, wrapper)
    del wrapper
    runner.release_step()
    if windows and world_size == 1:
        assert retained() is None
        assert not runner.has_wrappers
    else:
        assert retained() is not None
        assert runner.has_wrappers


def test_tiled_decode_preserves_dimensions_and_bounds_each_vae_call():
    class TiledVae(nn.Module):
        spatial_scale = 1
        latent_channels = 3

        def __init__(self) -> None:
            super().__init__()
            self.factor = mx.array(2.0)
            self.seen: list[tuple[int, int]] = []

        def decode(self, latents: mx.array) -> mx.array:
            self.seen.append((latents.shape[-2], latents.shape[-1]))
            return latents * self.factor

        def encode(self, image: mx.array) -> mx.array:
            return self.decode(image)

    with mx.stream(mx.Device(mx.cpu)):
        model = nn.Module()
        model.transformer = nn.Linear(1, 1)
        vae = TiledVae()
        model.vae = vae
        manager = WindowsImageMemoryManager(model)
        latents = mx.ones((1, 3, 1, 520, 520))
        with (
            mock.patch(
                "exo.worker.engines.image.windows_memory.read_gpu_memory",
                return_value=None,
            ),
            manager.stage(("vae",)),
        ):
            decoded = vae.decode(latents)
            mx.eval(decoded)
        assert decoded.shape == (1, 3, 520, 520)
        assert mx.allclose(decoded, mx.full(decoded.shape, 2.0)).item()
    assert len(vae.seen) > 1
    assert all(height <= 512 and width <= 512 for height, width in vae.seen)


def test_actual_free_vram_budget_forces_cpu_prompt_encoding():
    with mx.stream(mx.Device(mx.cpu)):
        model = SmallImageModel()
        manager = WindowsImageMemoryManager(model)
    with mock.patch(
        "exo.worker.engines.image.windows_memory.read_gpu_memory",
        return_value=_capacity(2560),
    ):
        with manager.stage(manager.prompt_components) as device:
            assert device == mx.Device(mx.cpu)
        with (
            pytest.raises(RuntimeError, match="activation reserve"),
            manager.stage(("transformer",), require_cuda=True),
        ):
            pass


def test_packed_quantized_weights_survive_gpu_staging():
    if not mx.cuda.is_available():
        pytest.skip("Requires a real MLX CUDA device")
    with mx.stream(mx.Device(mx.cpu)):
        model = nn.Module()
        transformer = nn.QuantizedLinear.from_linear(
            nn.Linear(64, 64), group_size=32, bits=4
        )
        model.transformer = transformer
        model.vae = SmallVae()
        manager = WindowsImageMemoryManager(model)
        inputs = mx.ones((1, 64))
        expected = transformer(inputs)
        mx.eval(expected)
    with (
        mock.patch(
            "exo.worker.engines.image.windows_memory.read_gpu_memory",
            return_value=_capacity(8 * 1024),
        ),
        manager.stage(("transformer",), require_cuda=True),
    ):
        actual = transformer(inputs)
        mx.eval(actual)
    with mx.stream(mx.Device(mx.cpu)):
        assert mx.allclose(actual, expected, atol=0.001).item()
