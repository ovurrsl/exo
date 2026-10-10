from pathlib import Path
from typing import cast
from unittest import mock

import mlx.core as mx
import pytest

from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.common import ModelId, NodeId
from exo.shared.types.memory import Memory
from exo.shared.types.worker.instances import BoundInstance, InstanceId, MlxRingInstance
from exo.shared.types.worker.runners import RunnerId, ShardAssignments
from exo.shared.types.worker.shards import PipelineShardMetadata
from exo.worker.engines.mlx import snapshot_guard
from exo.worker.engines.mlx.snapshot_guard import (
    model_contract_digest,
    snapshot_revision,
    verify_cuda_group_contract,
)


def _bound(end_layer: int = 2) -> BoundInstance:
    runner, node, model_id = RunnerId("runner"), NodeId("node"), ModelId("test/model")
    card = ModelCard(
        model_id=model_id,
        storage_size=Memory.from_mb(1),
        n_layers=2,
        hidden_size=8,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxCuda],
    )
    shard = PipelineShardMetadata(
        model_card=card,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=end_layer,
        n_layers=2,
    )
    return BoundInstance(
        instance=MlxRingInstance(
            instance_id=InstanceId("instance"),
            shard_assignments=ShardAssignments(
                model_id=model_id,
                runner_to_shard={runner: shard},
                node_to_runner={node: runner},
            ),
            hosts_by_node={},
            ephemeral_port=0,
        ),
        bound_runner_id=runner,
        bound_node_id=node,
    )


def _snapshot(path: Path) -> None:
    (path / "config.json").write_text("{}")
    (path / "model.safetensors").write_bytes(b"fixture")
    records = path / ".exo-revisions"
    records.mkdir()
    for name in ("config.json", "model.safetensors"):
        (records / f"{name}.revision").write_text("a" * 40 + "\n")


def test_hub_snapshot_metadata_is_accepted(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"fixture")
    records = tmp_path / ".cache" / "huggingface" / "download"
    records.mkdir(parents=True)
    for name in ("config.json", "model.safetensors"):
        (records / f"{name}.metadata").write_text("a" * 40 + "\netag\n1\n")
    assert snapshot_revision(tmp_path) == "a" * 40


def test_mixed_revisions_are_rejected_before_model_load(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"fixture")
    records = tmp_path / ".exo-revisions"
    records.mkdir()
    (records / "config.json.revision").write_text("a" * 40 + "\n")
    (records / "model.safetensors.revision").write_text("b" * 40 + "\n")
    with pytest.raises(ValueError, match="different"):
        snapshot_revision(tmp_path)


def test_unpinned_existing_download_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"fixture")
    with pytest.raises(ValueError, match="immutable"):
        snapshot_revision(tmp_path)


def test_empty_revision_record_is_a_handled_validation_error(tmp_path: Path) -> None:
    _snapshot(tmp_path)
    (tmp_path / ".exo-revisions" / "config.json.revision").write_text("")
    with pytest.raises(ValueError, match="Invalid snapshot revision"):
        snapshot_revision(tmp_path)


def test_empty_snapshot_cannot_pass_with_only_configuration(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    with pytest.raises(ValueError, match="no safetensors"):
        snapshot_revision(tmp_path)


def test_contract_changes_with_tokenizer_processor_and_layer_assignments(
    tmp_path: Path,
) -> None:
    _snapshot(tmp_path)
    baseline = model_contract_digest(_bound(), tmp_path)
    (tmp_path / "tokenizer_config.json").write_text('{"special_token": "changed"}')
    tokenizer = model_contract_digest(_bound(), tmp_path)
    (tmp_path / "preprocessor_config.json").write_text('{"size": 448}')
    processor = model_contract_digest(_bound(), tmp_path)
    assignment = model_contract_digest(_bound(end_layer=1), tmp_path)
    assert len({baseline, tokenizer, processor, assignment}) == 4


@pytest.mark.parametrize(
    "name",
    [
        "added_tokens.json",
        "spiece.model",
        "sentencepiece.bpe.model",
        "tekken.json",
        "processor_config.json",
    ],
)
def test_optional_tokenizer_and_processor_assets_are_bound_to_the_contract(
    tmp_path: Path, name: str
) -> None:
    _snapshot(tmp_path)
    missing = model_contract_digest(_bound(), tmp_path)
    (tmp_path / name).write_bytes(b"original tokenizer or processor content")
    original = model_contract_digest(_bound(), tmp_path)
    (tmp_path / name).write_bytes(b"modified tokenizer or processor content")
    modified = model_contract_digest(_bound(), tmp_path)
    assert len({missing, original, modified}) == 3


class _TwoRanks:
    def size(self) -> int:
        return 2


def test_local_io_error_still_participates_in_the_collective() -> None:
    group = cast(mx.distributed.Group, cast(object, _TwoRanks()))
    participated: list[bool] = []

    def gather(
        row: mx.array,
        *,
        group: mx.distributed.Group | None,
        stream: mx.Stream | mx.Device | None,
    ) -> mx.array:
        assert group is not None and stream == mx.Device(mx.cpu)
        values = cast(list[int], row.tolist())
        assert values[0] == 0
        participated.append(True)
        return mx.array(values + [1, *bytes(32)], dtype=mx.int32)

    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(
            snapshot_guard, "model_contract_digest", side_effect=OSError("unreadable")
        ),
        mock.patch.object(
            snapshot_guard, "build_model_path", return_value=Path("missing")
        ),
        mock.patch.object(mx.distributed, "all_gather", gather),
        pytest.raises(RuntimeError, match="unreadable"),
    ):
        verify_cuda_group_contract(_bound(), group)
    assert participated == [True]


def test_valid_local_rank_rejects_mismatched_peer_contract() -> None:
    group = cast(mx.distributed.Group, cast(object, _TwoRanks()))

    def gather(
        row: mx.array,
        *,
        group: mx.distributed.Group | None,
        stream: mx.Stream | mx.Device | None,
    ) -> mx.array:
        values = cast(list[int], row.tolist())
        peer = values.copy()
        peer[-1] ^= 1
        return mx.array(values + peer, dtype=mx.int32)

    with (
        mx.stream(mx.Device(mx.cpu)),
        mock.patch.object(
            snapshot_guard, "model_contract_digest", return_value=bytes(32)
        ),
        mock.patch.object(
            snapshot_guard, "build_model_path", return_value=Path("unused")
        ),
        mock.patch.object(mx.distributed, "all_gather", gather),
        pytest.raises(RuntimeError, match="differ"),
    ):
        verify_cuda_group_contract(_bound(), group)
