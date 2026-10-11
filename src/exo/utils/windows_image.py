"""Fail closed before constructing the pinned Windows CUDA image model."""

import hashlib
import sys
from pathlib import Path

import psutil

from exo.shared.models.windows_image_budget import (
    WINDOWS_IMAGE_CUDA_RESERVE,
    WindowsImageBudget,
    get_windows_image_budget,
)
from exo.shared.types.common import ModelId
from exo.shared.types.worker.shards import CfgShardMetadata, PipelineShardMetadata
from exo.utils.windows_gpu import read_gpu_memory

# Verified immutable model payloads and tokenizer/index assets. Both HF commit
# records and content hashes must match; a current mutable "main" is insufficient.
SNAPSHOT_ASSETS: tuple[tuple[str, int, str], ...] = (
    (
        "text_encoder/0.safetensors",
        69436582,
        "bed7a5d5508c439a8c2f4bee65facb983ad5b51ed62eabb9d0bbebef38641751",
    ),
    (
        "text_encoder_2/0.safetensors",
        2145878330,
        "c6276bb5ce76b96f8749a11ea260d44b4e4086638289993d63759f5863bd9a24",
    ),
    (
        "text_encoder_2/1.safetensors",
        533312161,
        "d60843d0ba4fa6a3675afcef08d089f32b3f1f9e6a0547d0deac76e0fffda2d2",
    ),
    (
        "transformer/0.safetensors",
        2123862672,
        "7d5c58a05745e3c9440364863eada6de7e81fc9e0531c6cdaa475683c774d99f",
    ),
    (
        "transformer/1.safetensors",
        2141393618,
        "b3cce266fa201de3aa3b1a48d4d1deb0a70d97ac6574f88a2e09e491223a4fa3",
    ),
    (
        "transformer/2.safetensors",
        2130572514,
        "5832fe7c8238f27ac38abc9a78ea5e0e7d7bf5154df99086973dea95a0205937",
    ),
    (
        "transformer/3.safetensors",
        297640239,
        "c39388e3d20a0c69c647780e4399b5585d6dddf72e829290574c541d718eddae",
    ),
    (
        "vae/0.safetensors",
        164654152,
        "69fe087c512933d1755e759caed00459050763e9a03e5deb8059b96e19880cc1",
    ),
    (
        "text_encoder/model.safetensors.index.json",
        25036,
        "61644bd97ad188ce646211e281f45c6b52270501998e64f24d749cc275e49595",
    ),
    (
        "text_encoder_2/model.safetensors.index.json",
        44071,
        "62e965384e5f3395de7be07a9927b7554b3db786bb2465101ed6d15c3dc73958",
    ),
    (
        "tokenizer/tokenizer.json",
        3642073,
        "6d9109cc838977f3ca94a379eec36aecc7c807e1785cd729660ca2fc0171fb35",
    ),
    (
        "tokenizer/tokenizer_config.json",
        361,
        "db8163780d5eb21ec720559e5ef306f2dfc2208dc55f45362e5623bbe9fcd5d2",
    ),
    (
        "tokenizer_2/tokenizer.json",
        2107290,
        "bae0cc14052af3b7df524bd5d976ddf676ddb53189b992f725838c4e1ae69d4b",
    ),
    (
        "tokenizer_2/tokenizer_config.json",
        2437,
        "a6db72fd2d8f83f38435d6d01880327c07541896f612808d3c761e6103024b6d",
    ),
    (
        "transformer/model.safetensors.index.json",
        146325,
        "2e521afd3a26f9db9893b86933ec2cab1d6fbdbd733c24266b106b3a54ea0a35",
    ),
    (
        "vae/model.safetensors.index.json",
        17385,
        "ae3f0747974d6dad55bbe5aff27a6c9fda9a78875a14abb8bceb127ee59f948b",
    ),
)


def _host_available_bytes() -> int:
    available: int = psutil.virtual_memory().available
    return available


def _validate_snapshot(model_path: Path, budget: WindowsImageBudget) -> None:
    for relative_name, size, digest in SNAPSHOT_ASSETS:
        relative = Path(relative_name)
        path = model_path / relative
        if not path.is_file() or path.stat().st_size != size:
            raise ValueError(
                f"Incomplete qualified Windows image snapshot: {relative_name}"
            )
        exo_record = (
            model_path
            / ".exo-revisions"
            / relative.with_suffix(relative.suffix + ".revision")
        )
        hf_record = (
            model_path
            / ".cache/huggingface/download"
            / relative.with_suffix(relative.suffix + ".metadata")
        )
        record = exo_record if exo_record.is_file() else hf_record
        if not record.is_file():
            raise ValueError(
                f"Missing immutable image snapshot record for {relative_name}"
            )
        lines = record.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != budget.snapshot_revision:
            raise ValueError(
                f"The Windows image snapshot revision is not qualified: {relative_name}"
            )
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError(
                    f"Windows image snapshot content digest differs: {relative_name}"
                )


def validate_windows_image_model(
    model_id: ModelId,
    model_path: Path,
    shard: PipelineShardMetadata | CfgShardMetadata,
) -> None:
    if sys.platform != "win32":
        return
    budget = get_windows_image_budget(model_id)
    if budget is None:
        raise ValueError("This Windows CUDA image family/precision is not qualified")
    if (
        not isinstance(shard, PipelineShardMetadata)
        or shard.model_card.model_id != model_id
        or shard.device_rank != 0
        or shard.world_size != 1
        or shard.n_layers != budget.n_layers
        or shard.start_layer != 0
        or shard.end_layer != budget.n_layers
    ):
        raise ValueError(
            "Qualified Windows CUDA image generation requires a single complete local shard"
        )
    available_host = _host_available_bytes()
    if available_host < budget.minimum_host_memory.in_bytes:
        raise MemoryError(
            "The pinned Windows image model requires "
            f"{budget.minimum_host_memory.in_gb:.2f} GiB free host RAM, "
            f"but only {available_host / 1024**3:.2f} GiB is available"
        )
    memory = read_gpu_memory()
    if memory is None:
        raise RuntimeError("NVIDIA memory capacity is unavailable for image generation")
    available_gpu = memory.free - WINDOWS_IMAGE_CUDA_RESERVE
    required_gpu = budget.minimum_gpu_memory(shard.start_layer, shard.end_layer)
    if available_gpu < required_gpu:
        raise MemoryError(
            f"Windows image GPU stages need {required_gpu.in_gb:.2f} GiB of weights; "
            f"only {max(0, available_gpu.in_bytes) / 1024**3:.2f} GiB is free "
            "after the CUDA activation reserve"
        )
    _validate_snapshot(model_path, budget)
