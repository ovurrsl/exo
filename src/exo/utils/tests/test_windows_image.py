import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.models.windows_image_budget import (
    WINDOWS_IMAGE_CUDA_RESERVE,
    get_windows_image_budget,
)
from exo.shared.types.backends import Backend
from exo.shared.types.common import ModelId
from exo.shared.types.memory import Memory
from exo.shared.types.worker.shards import PipelineShardMetadata
from exo.utils import windows_image
from exo.utils.windows_gpu import GpuMemory

_MODEL_ID = ModelId("exolabs/FLUX.1-schnell-4bit")


def _shard(*, world_size: int = 1) -> PipelineShardMetadata:
    return PipelineShardMetadata(
        model_card=ModelCard(
            model_id=_MODEL_ID,
            n_layers=57,
            hidden_size=1,
            storage_size=Memory.from_gb(15),
            supports_tensor=False,
            tasks=[ModelTask.TextToImage],
            backends=[Backend.MlxMetal],
        ),
        device_rank=0,
        world_size=world_size,
        start_layer=0,
        end_layer=57,
        n_layers=57,
    )


@pytest.fixture
def pinned_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    budget = get_windows_image_budget(_MODEL_ID)
    assert budget is not None
    data = b"pinned accepted tensor contents"
    path = tmp_path / "transformer" / "0.safetensors"
    path.parent.mkdir()
    path.write_bytes(data)
    record = tmp_path / ".cache/huggingface/download/transformer/0.safetensors.metadata"
    record.parent.mkdir(parents=True)
    record.write_text(budget.snapshot_revision + "\nfixture-etag\n")
    monkeypatch.setattr(
        windows_image,
        "SNAPSHOT_ASSETS",
        (("transformer/0.safetensors", len(data), hashlib.sha256(data).hexdigest()),),
    )
    monkeypatch.setattr(windows_image, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(windows_image, "_host_available_bytes", lambda: 32 * 1024**3)
    monkeypatch.setattr(
        windows_image,
        "read_gpu_memory",
        lambda: GpuMemory(Memory.from_gb(12), Memory.from_gb(11)),
    )
    return tmp_path


def test_complete_pinned_snapshot_accepts_actual_capacity(pinned_model: Path) -> None:
    windows_image.validate_windows_image_model(_MODEL_ID, pinned_model, _shard())


def test_wrong_revision_rejects_before_model_materialization(
    pinned_model: Path,
) -> None:
    record = (
        pinned_model / ".cache/huggingface/download/transformer/0.safetensors.metadata"
    )
    record.write_text("a" * 40 + "\nfixture-etag\n")
    with pytest.raises(ValueError, match="snapshot"):
        windows_image.validate_windows_image_model(_MODEL_ID, pinned_model, _shard())


def test_same_size_modified_weights_reject_even_with_correct_commit_record(
    pinned_model: Path,
) -> None:
    weights = pinned_model / "transformer/0.safetensors"
    weights.write_bytes(b"x" * weights.stat().st_size)
    with pytest.raises(ValueError, match="digest"):
        windows_image.validate_windows_image_model(_MODEL_ID, pinned_model, _shard())


def test_host_capacity_is_distinct_from_gpu_capacity(
    pinned_model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget = get_windows_image_budget(_MODEL_ID)
    assert budget is not None
    monkeypatch.setattr(
        windows_image,
        "_host_available_bytes",
        lambda: budget.minimum_host_memory.in_bytes - 1,
    )
    with pytest.raises(MemoryError, match="host RAM"):
        windows_image.validate_windows_image_model(_MODEL_ID, pinned_model, _shard())


def test_large_host_capacity_cannot_credit_missing_gpu_reserve(
    pinned_model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget = get_windows_image_budget(_MODEL_ID)
    assert budget is not None
    monkeypatch.setattr(windows_image, "_host_available_bytes", lambda: 128 * 1024**3)
    free = (
        budget.minimum_gpu_memory(0, 57)
        + WINDOWS_IMAGE_CUDA_RESERVE
        - Memory.from_bytes(1)
    )
    monkeypatch.setattr(
        windows_image, "read_gpu_memory", lambda: GpuMemory(Memory.from_gb(12), free)
    )
    with pytest.raises(MemoryError, match="GPU"):
        windows_image.validate_windows_image_model(_MODEL_ID, pinned_model, _shard())


def test_nvml_loss_rejects_even_with_host_capacity(
    pinned_model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(windows_image, "read_gpu_memory", lambda: None)
    with pytest.raises(RuntimeError, match="NVIDIA"):
        windows_image.validate_windows_image_model(_MODEL_ID, pinned_model, _shard())


def test_unqualified_peer_and_image_family_are_rejected(pinned_model: Path) -> None:
    with pytest.raises(ValueError, match="single"):
        windows_image.validate_windows_image_model(
            _MODEL_ID, pinned_model, _shard(world_size=2)
        )
    with pytest.raises(ValueError, match="qualified"):
        windows_image.validate_windows_image_model(
            ModelId("exolabs/FLUX.1-dev-4bit"), pinned_model, _shard()
        )


def test_mac_path_does_not_query_nvidia_or_read_pinned_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(windows_image, "sys", SimpleNamespace(platform="darwin"))

    def fail_if_called() -> GpuMemory:
        raise AssertionError("Mac must not read Windows image capacity")

    monkeypatch.setattr(windows_image, "read_gpu_memory", fail_if_called)
    windows_image.validate_windows_image_model(_MODEL_ID, Path("missing"), _shard())
