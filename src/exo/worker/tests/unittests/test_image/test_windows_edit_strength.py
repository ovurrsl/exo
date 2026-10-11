"""Windows edits must retain input conditioning while Mac calls stay unchanged."""

import base64
import io
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest import mock

import pytest
from mflux.models.common.config.config import Config
from mflux.models.common.config.model_config import ModelConfig
from PIL import Image

from exo.api.types import (
    AdvancedImageParams,
    ImageEditsTaskParams,
    ImageGenerationTaskParams,
)
from exo.shared.types.common import ModelId
from exo.worker.engines.image.distributed_model import DistributedImageModel
from exo.worker.engines.image.generate import generate_image
from exo.worker.engines.image.models import get_config_for_model

MODEL = ModelId("exolabs/FLUX.1-schnell-4bit")


class CaptureModel:
    model_id = MODEL

    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def generate(self, **options: object) -> Iterator[Image.Image]:
        self.options = options
        yield Image.new("RGB", (16, 16))


def edit_task(strength: float) -> ImageEditsTaskParams:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (220, 30, 30)).save(buffer, format="PNG")
    return ImageEditsTaskParams(
        model=MODEL,
        prompt="Change the background",
        image_data=base64.b64encode(buffer.getvalue()).decode("ascii"),
        image_strength=strength,
        size="512x512",
    )


@pytest.mark.parametrize("strength", [0.3, 0.7])
def test_windows_edit_forwards_requested_fidelity(strength: float) -> None:
    capture = CaptureModel()
    with mock.patch("sys.platform", "win32"):
        _ = list(
            generate_image(
                cast(DistributedImageModel, cast(object, capture)), edit_task(strength)
            )
        )
    assert capture.options.get("image_strength") == strength


def test_mac_edit_keeps_existing_model_call() -> None:
    capture = CaptureModel()
    with mock.patch("sys.platform", "darwin"):
        _ = list(
            generate_image(
                cast(DistributedImageModel, cast(object, capture)), edit_task(0.7)
            )
        )
    assert "image_strength" not in capture.options


def test_windows_text_generation_keeps_existing_model_call() -> None:
    capture = CaptureModel()
    task = ImageGenerationTaskParams(model=MODEL, prompt="A red apple", size="512x512")
    with mock.patch("sys.platform", "win32"):
        _ = list(
            generate_image(cast(DistributedImageModel, cast(object, capture)), task)
        )
    assert "image_strength" not in capture.options


class CaptureAdapter:
    def __init__(self) -> None:
        self.model = self
        self.model_config = ModelConfig.from_name(model_name=MODEL, base_model=None)

    def set_image_dimensions(self, image_path: Path) -> None:
        del image_path


class CaptureRunner:
    def __init__(self) -> None:
        self.config: Config | None = None

    def generate_image(
        self, runtime_config: Config, **options: object
    ) -> Iterator[Image.Image]:
        del options
        self.config = runtime_config
        yield Image.new("RGB", (16, 16))


@pytest.mark.parametrize(
    "platform,strength,timestep",
    [("win32", 0.3, 1), ("win32", 0.7, 2), ("darwin", 0.7, 0)],
)
def test_windows_fidelity_selects_img2img_timestep_and_mac_keeps_baseline(
    platform: str, strength: float, timestep: int
) -> None:
    model = object.__new__(DistributedImageModel)
    runner = CaptureRunner()
    vars(model).update(
        {
            "_config": get_config_for_model(MODEL),
            "_adapter": CaptureAdapter(),
            "_runner": runner,
        }
    )
    with mock.patch(
        "exo.worker.engines.image.distributed_model.sys.platform", platform
    ):
        _ = list(
            model.generate(
                prompt="A red apple",
                height=16,
                width=16,
                image_path=Path("input.png"),
                image_strength=strength,
                advanced_params=AdvancedImageParams(num_inference_steps=4),
            )
        )
    assert runner.config is not None
    assert runner.config.init_time_step == timestep
    assert runner.config.image_strength == (strength if platform == "win32" else None)
