"""Pinned, offline full-model Windows diffusion staging acceptance gate."""

import argparse
import hashlib
import json
import os
import time
import tomllib
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-preflight", action="store_true")
    arguments = parser.parse_args()
    model_path = arguments.model_path.resolve()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["EXO_MODELS_READ_ONLY_DIRS"] = str(model_path.parent)
    os.environ["EXO_HOME"] = str(output / "exo-home")
    from exo.utils.rlimits import install_windows_resource_shim

    install_windows_resource_shim()
    import mlx.core as mx
    import numpy as np
    import psutil
    from PIL import Image

    from exo.api.types import AdvancedImageParams
    from exo.shared.models.model_cards import ModelCard
    from exo.shared.types.worker.shards import PipelineShardMetadata
    from exo.utils.windows_gpu import read_gpu_memory
    from exo.worker.engines.image.distributed_model import DistributedImageModel

    assert mx.cuda.is_available(), "Actual Windows CUDA hardware is required"
    card_path = Path("resources/image_model_cards/exolabs--FLUX.1-schnell-4bit.toml")
    card = ModelCard.model_validate(tomllib.loads(card_path.read_text()))
    shard = PipelineShardMetadata(
        model_card=card,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=card.n_layers,
        n_layers=card.n_layers,
    )
    report = {
        "model_id": card.model_id,
        "mlx_version": version("mlx"),
        "model_path": str(model_path),
        "passed": False,
        "scope": "Full local Windows text-to-image pipeline, partial decode and cancellation/recovery. Large CPU fallback, image editing and physical Mac peer remain unqualified.",
        "stages": [],
    }

    def record(name, details):
        report["stages"].append({"name": name, **details})
        report["mlx_peak_allocation_bytes"] = mx.get_peak_memory()
        report["process_rss_bytes"] = psutil.Process().memory_info().rss
        (output / "image.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["stages"][-1]), flush=True)

    started = time.monotonic()
    model = DistributedImageModel(card.model_id, model_path, shard, None)
    manager = model._runner._windows_memory
    assert manager is not None
    stage_observations = []
    step_observations = []
    report["production_stages"] = stage_observations
    report["evaluated_denoise_steps"] = step_observations
    phase = "initial_generation"
    real_stage = manager.stage

    @contextmanager
    def observe_stage(names, *, require_cuda=False):
        # This observer delegates all staging, computation and cleanup to the
        # unchanged production context. It does not emulate any model/device.
        with real_stage(names, require_cuda=require_cuda) as device:
            observation = {
                "phase": phase,
                "components": list(names),
                "device": str(device),
                "required_cuda": require_cuda,
                "mlx_active_allocation_on_enter_bytes": mx.get_active_memory(),
            }
            stage_observations.append(observation)
            memory = read_gpu_memory()
            assert memory is not None
            observation["actual_nvml_used_on_enter_bytes"] = (
                memory.total.in_bytes - memory.free.in_bytes
            )
            record("stage_enter", observation.copy())
            yield device
            observation["mlx_active_allocation_before_offload_bytes"] = (
                mx.get_active_memory()
            )
        memory = read_gpu_memory()
        assert memory is not None
        record(
            "stage_exit",
            {
                "phase": phase,
                "components": list(names),
                "remaining_active_components": list(manager.active_components),
                "actual_nvml_used_after_offload_bytes": memory.total.in_bytes
                - memory.free.in_bytes,
            },
        )

    manager.stage = observe_stage

    class StepObserver:
        def call_in_loop(self, t, seed, prompt, latents, config, time_steps):
            mx.eval(latents)
            assert bool(mx.all(mx.isfinite(latents)))
            assert manager._active == ("transformer",)
            assert manager._device == mx.Device(mx.gpu)
            step_observations.append(
                {
                    "phase": phase,
                    "step": t,
                    "device": str(manager._device),
                    "latent_shape": list(latents.shape),
                    "mlx_active_allocation_bytes": mx.get_active_memory(),
                }
            )
            record("evaluated_denoise_step", step_observations[-1].copy())

    model._adapter.model.callbacks.register(StepObserver())
    record(
        "host_construction",
        {
            "duration_seconds": time.monotonic() - started,
            "mlx_active_allocation_bytes": mx.get_active_memory(),
            "component_weight_bytes": {
                name: component.bytes for name, component in manager._components.items()
            },
        },
    )
    # All canonical host parameters remain attached after construction. Running
    # actual encoders with the CPU stream qualifies the fallback computations.
    if arguments.cpu_preflight:
        started = time.monotonic()
        cpu = mx.Device(mx.cpu)
        with mx.stream(cpu):
            prompt_data = model._adapter.encode_prompt(
                "A red apple for the CPU encoder check"
            )
            embeddings = prompt_data.prompt_embeds
            mx.eval(embeddings)
            assert bool(mx.all(mx.isfinite(embeddings)))
        record(
            "cpu_prompt_encoders",
            {
                "duration_seconds": time.monotonic() - started,
                "shape": embeddings.shape,
                "device": str(cpu),
            },
        )
        started = time.monotonic()
        with mx.stream(cpu):
            decoded = model._adapter.model.vae.decode(
                mx.zeros((1, 16, 1, 32, 32), dtype=mx.bfloat16)
            )
            mx.eval(decoded)
            assert bool(mx.all(mx.isfinite(decoded)))
            assert decoded.shape[-2:] == (256, 256)
        record(
            "cpu_vae_decode",
            {
                "duration_seconds": time.monotonic() - started,
                "shape": decoded.shape,
                "device": str(cpu),
            },
        )
        del decoded, prompt_data, embeddings
    started = time.monotonic()
    images = list(
        model.generate(
            prompt="A red apple on a white background",
            height=256,
            width=256,
            seed=2,
            partial_images=1,
            advanced_params=AdvancedImageParams(num_inference_steps=4),
        )
    )
    assert len(images) == 2, "Expected a real partial decode and final image"
    partial, final = images
    assert isinstance(partial, tuple)
    assert isinstance(final, Image.Image) and final.size == (256, 256)
    partial_image = partial[0]
    assert partial_image.size == final.size
    pixels = np.asarray(final)
    assert float(pixels.std()) > 1, "Generated image is empty or constant"
    partial_image.save(output / "partial.png")
    final.save(output / "generated.png")
    record(
        "generation_and_partial_decode",
        {
            "duration_seconds": time.monotonic() - started,
            "size": final.size,
            "pixel_standard_deviation": float(pixels.std()),
            "image_sha256": hashlib.sha256(
                (output / "generated.png").read_bytes()
            ).hexdigest(),
            "production_stages": stage_observations.copy(),
            "evaluated_denoise_steps": step_observations.copy(),
        },
    )
    assert len(step_observations) == 4
    assert manager._active == ()
    started = time.monotonic()
    phase = "cancel_after_one_real_step"

    def cancel_after_step():
        return any(item["phase"] == phase for item in step_observations)

    cancelled = list(
        model.generate(
            prompt="A blue apple for cancellation",
            height=256,
            width=256,
            seed=3,
            cancel_checker=cancel_after_step,
            advanced_params=AdvancedImageParams(num_inference_steps=4),
        )
    )
    assert cancelled == [], "Cancellation produced a final image"
    assert manager._active == (), "Cancellation retained GPU component parameters"
    cancelled_steps = [item for item in step_observations if item["phase"] == phase]
    assert len(cancelled_steps) == 1, "Expected cancellation after one actual step"
    record(
        "cancel_after_one_real_step",
        {
            "duration_seconds": time.monotonic() - started,
            "evaluated_denoise_steps": cancelled_steps,
            "active_components_after_cancel": list(manager._active),
            "mlx_active_allocation_after_cancel_bytes": mx.get_active_memory(),
        },
    )
    started = time.monotonic()
    phase = "recovery_generation"
    recovered = list(
        model.generate(
            prompt="A red apple on a white background",
            height=256,
            width=256,
            seed=2,
            advanced_params=AdvancedImageParams(num_inference_steps=4),
        )
    )
    assert len(recovered) == 1 and isinstance(recovered[0], Image.Image)
    assert recovered[0].size == (256, 256)
    assert np.array_equal(np.asarray(recovered[0]), pixels)
    assert manager._active == ()
    recovery_steps = [item for item in step_observations if item["phase"] == phase]
    assert len(recovery_steps) == 4
    recovered[0].save(output / "recovered.png")
    record(
        "recovery_generation",
        {
            "duration_seconds": time.monotonic() - started,
            "evaluated_denoise_steps": recovery_steps,
            "matches_original_pixels": True,
            "production_stages": stage_observations,
        },
    )
    started = time.monotonic()
    phase = "overlap_tiled_vae"
    with manager.stage(("vae",)):
        decoded = model._adapter.model.vae.decode(
            mx.zeros((1, 16, 1, 65, 65), dtype=mx.bfloat16)
        )
        mx.eval(decoded)
        assert bool(mx.all(mx.isfinite(decoded)))
        assert decoded.shape[-2:] == (520, 520)
    assert manager.active_components == ()
    record(
        "real_model_overlap_tiled_vae",
        {"duration_seconds": time.monotonic() - started, "shape": decoded.shape},
    )
    report["passed"] = True
    (output / "image.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            json.dumps({"error": type(error).__name__, "detail": str(error)}),
            flush=True,
        )
        raise
