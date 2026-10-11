"""Check CUDA group model contracts on the existing CPU ring, before loading."""

import hashlib
import json
from pathlib import Path
from typing import cast

import mlx.core as mx

from exo.download.download_utils import build_model_path
from exo.shared.types.worker.instances import BoundInstance


def snapshot_revision(model_path: Path) -> str:
    config = model_path / "config.json"
    if not config.is_file():
        raise ValueError("The model snapshot has no config.json")
    weights = sorted(model_path.rglob("*.safetensors"))
    if not weights:
        raise ValueError("The model snapshot has no safetensors weights")
    revisions: set[str] = set()
    for path in [config, *weights]:
        relative = path.relative_to(model_path)
        exo_record = (
            model_path
            / ".exo-revisions"
            / relative.with_suffix(relative.suffix + ".revision")
        )
        hub_record = (
            model_path
            / ".cache"
            / "huggingface"
            / "download"
            / relative.with_suffix(relative.suffix + ".metadata")
        )
        record = exo_record if exo_record.is_file() else hub_record
        if not record.is_file():
            raise ValueError(
                f"No immutable snapshot record for {relative}; stage the same pinned "
                "Hugging Face snapshot on every rank before creating a CUDA group"
            )
        lines = record.read_text(encoding="utf-8").splitlines()
        revision = lines[0].strip() if lines else ""
        if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError(f"Invalid snapshot revision for {relative}")
        revisions.add(revision)
    if len(revisions) != 1:
        raise ValueError("Model files belong to different Hugging Face snapshots")
    return next(iter(revisions))


def model_contract_digest(bound_instance: BoundInstance, model_path: Path) -> bytes:
    digest = hashlib.sha256()
    digest.update(snapshot_revision(model_path).encode("ascii"))
    assignments = json.dumps(
        bound_instance.instance.shard_assignments.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest.update(hashlib.sha256(assignments).digest())
    # Weight shards can differ by rank. Tokenization/configuration must not.
    names = (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "tokenizer.model",
        "added_tokens.json",
        "spiece.model",
        "sentencepiece.bpe.model",
        "tekken.json",
        "vocab.json",
        "merges.txt",
        "special_tokens_map.json",
        "chat_template.jinja",
        "chat_template.json",
        "generation_config.json",
        "preprocessor_config.json",
        "processor_config.json",
        "video_preprocessor_config.json",
        "model.safetensors.index.json",
    )
    for name in names:
        path = model_path / name
        digest.update(name.encode("ascii") + b"\0")
        if path.is_file():
            file_digest = hashlib.sha256()
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    file_digest.update(block)
            digest.update(b"\1" + file_digest.digest())
        else:
            digest.update(b"\0")
    return digest.digest()


def verify_cuda_group_contract(
    bound_instance: BoundInstance, group: mx.distributed.Group
) -> None:
    error: str | None = None
    try:
        digest = model_contract_digest(
            bound_instance,
            build_model_path(bound_instance.bound_shard.model_card.model_id),
        )
    except (OSError, ValueError) as exception:
        error = str(exception)
        digest = bytes(32)
    cpu = mx.Device(mx.cpu)
    with mx.stream(cpu):
        contracts = mx.distributed.all_gather(
            mx.array([int(error is None), *digest], dtype=mx.int32),
            group=group,
            stream=cpu,
        ).reshape(group.size(), 33)
        rows = cast(list[list[int]], contracts.tolist())
    if any(row[0] != 1 for row in rows):
        raise RuntimeError(error or "A CUDA group peer has an invalid model snapshot")
    if any(row != rows[0] for row in rows[1:]):
        raise RuntimeError(
            "CUDA group model snapshot, tokenizer, precision or layer assignments differ"
        )
