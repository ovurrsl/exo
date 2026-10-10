from typing import TypedDict

import pytest

from exo.master import placement as placement_module
from exo.master.placement import place_instance
from exo.master.tests.conftest import create_node_memory, create_node_network
from exo.master.windows_text_placement import (
    cuda_text_instance_memory,
    cuda_text_memory_requirement,
)
from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.topology import Topology
from exo.shared.types.backends import Backend
from exo.shared.types.commands import PlaceInstance
from exo.shared.types.common import ModelId, NodeId
from exo.shared.types.memory import Memory
from exo.shared.types.worker.instances import Instance, InstanceId, InstanceMeta
from exo.shared.types.worker.shards import Sharding
from exo.utils.windows_text_offload_config import WindowsTextOffloadPolicy


class OffloadOptions(TypedDict):
    offload_policy: WindowsTextOffloadPolicy
    local_node_id: NodeId
    host_available_bytes: int


def card(base: str = "Qwen3 32B") -> ModelCard:
    return ModelCard(
        model_id=ModelId("test/Qwen3-32B-4bit"),
        storage_size=Memory.from_gb(20),
        n_layers=40,
        hidden_size=4096,
        supports_tensor=True,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxCuda],
        base_model=base,
        quantization="4bit",
    )


def test_only_local_enabled_dense_windows_cuda_qualifies() -> None:
    local, remote = NodeId(), NodeId()
    model = card()
    policy = WindowsTextOffloadPolicy(
        enabled=True, host_limit_bytes=64 * 1024**3, stage_limit_bytes=1024**3
    )
    options = OffloadOptions(
        offload_policy=policy, local_node_id=local, host_available_bytes=64 * 1024**3
    )
    assert cuda_text_memory_requirement(
        model, [local], {local: [Backend.MlxCuda]}, {local}, **options
    ) == Memory.from_gb(1.5)
    cases: tuple[tuple[list[NodeId], set[NodeId], str], ...] = (
        ([remote], {remote}, "Qwen3 32B"),
        ([local, remote], {local}, "Qwen3 32B"),
        ([local], set(), "Qwen3 32B"),
        ([local], {local}, "Qwen3.5 27B"),
        ([local], {local}, "Qwen3 30B A3B"),
    )
    for nodes, windows, base in cases:
        assert (
            cuda_text_memory_requirement(
                card(base),
                nodes,
                {node: [Backend.MlxCuda] for node in nodes},
                windows,
                **options,
            )
            is None
        )
    disabled_options = options.copy()
    disabled_options["offload_policy"] = WindowsTextOffloadPolicy()
    assert (
        cuda_text_memory_requirement(
            model,
            [local],
            {local: [Backend.MlxCuda]},
            {local},
            **disabled_options,
        )
        is None
    )


def test_host_budget_is_separate_from_vram() -> None:
    local = NodeId()
    with pytest.raises(ValueError, match="host"):
        cuda_text_memory_requirement(
            card(),
            [local],
            {local: [Backend.MlxCuda]},
            {local},
            offload_policy=WindowsTextOffloadPolicy(
                enabled=True, host_limit_bytes=64 * 1024**3, stage_limit_bytes=1024**3
            ),
            local_node_id=local,
            host_available_bytes=1,
        )


def test_full_singleton_placement_exceeds_vram_without_mutating_storage() -> None:
    local = NodeId()
    topology = Topology()
    topology.add_node(local)
    model = card()
    instances: dict[InstanceId, Instance] = {}
    args = (
        PlaceInstance(
            model_card=model,
            sharding=Sharding.Pipeline,
            instance_meta=InstanceMeta.MlxRing,
            min_nodes=1,
        ),
        topology,
        instances,
        {local: create_node_memory(2 * 1024**3)},
        {local: create_node_network()},
        {local: [Backend.MlxCuda]},
    )
    with pytest.raises(ValueError, match="sufficient memory"):
        place_instance(*args, windows_node_ids={local})
    placements = place_instance(
        *args,
        windows_node_ids={local},
        offload_policy=WindowsTextOffloadPolicy(
            enabled=True, host_limit_bytes=64 * 1024**3, stage_limit_bytes=1024**3
        ),
        local_node_id=local,
        host_available_bytes=64 * 1024**3,
    )
    shard = next(
        iter(next(iter(placements.values())).shard_assignments.runner_to_shard.values())
    )
    assert (shard.start_layer, shard.end_layer, shard.world_size) == (0, 40, 1)
    assert shard.model_card.storage_size == Memory.from_gb(20)
    with pytest.raises(ValueError, match="sufficient memory"):
        place_instance(
            args[0],
            topology,
            instances,
            {local: create_node_memory(Memory.from_gb(1.5).in_bytes - 1)},
            {local: create_node_network()},
            {local: [Backend.MlxCuda]},
            windows_node_ids={local},
            local_node_id=local,
            offload_policy=WindowsTextOffloadPolicy(
                enabled=True, host_limit_bytes=64 * 1024**3, stage_limit_bytes=1024**3
            ),
            host_available_bytes=64 * 1024**3,
        )
    instance = next(iter(placements.values()))
    runner = next(iter(instance.shard_assignments.runner_to_shard))
    invalid = instance.model_copy(
        update={
            "shard_assignments": instance.shard_assignments.model_copy(
                update={
                    "runner_to_shard": {
                        runner: shard.model_copy(update={"end_layer": 20})
                    }
                }
            )
        }
    )
    with pytest.raises(ValueError, match="full qualified shard"):
        cuda_text_instance_memory(
            invalid,
            model,
            {local: [Backend.MlxCuda]},
            {local},
            offload_policy=WindowsTextOffloadPolicy(
                enabled=True, host_limit_bytes=64 * 1024**3, stage_limit_bytes=1024**3
            ),
            local_node_id=local,
            host_available_bytes=64 * 1024**3,
        )


def test_insufficient_vram_and_stage_budget_fail_closed() -> None:
    local = NodeId()
    options = OffloadOptions(
        offload_policy=WindowsTextOffloadPolicy(
            enabled=True, host_limit_bytes=64 * 1024**3, stage_limit_bytes=1
        ),
        local_node_id=local,
        host_available_bytes=64 * 1024**3,
    )
    with pytest.raises(ValueError, match="stage"):
        cuda_text_memory_requirement(
            card(), [local], {local: [Backend.MlxCuda]}, {local}, **options
        )
    assert (
        cuda_text_memory_requirement(
            card().model_copy(update={"quantization": "6bit"}),
            [local],
            {local: [Backend.MlxCuda]},
            {local},
            **options,
        )
        is None
    )


def test_host_limit_caps_weights_and_actual_free_memory_covers_headroom() -> None:
    local = NodeId()
    model = card()
    policy = WindowsTextOffloadPolicy(
        enabled=True,
        host_limit_bytes=model.storage_size.in_bytes,
        stage_limit_bytes=1024**3,
    )
    assert (
        cuda_text_memory_requirement(
            model,
            [local],
            {local: [Backend.MlxCuda]},
            {local},
            offload_policy=policy,
            local_node_id=local,
            host_available_bytes=64 * 1024**3,
        )
        is not None
    )
    with pytest.raises(ValueError, match="host"):
        cuda_text_memory_requirement(
            model,
            [local],
            {local: [Backend.MlxCuda]},
            {local},
            offload_policy=policy,
            local_node_id=local,
            host_available_bytes=model.storage_size.in_bytes,
        )


def test_normal_vram_fit_skips_offload_and_host_policy_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local = NodeId()
    topology = Topology()
    topology.add_node(local)
    model = card()

    def reject_staging(*_arguments: object, **_options: object) -> None:
        raise AssertionError("A normal VRAM fit must not use offload admission")

    monkeypatch.setattr(
        placement_module, "cuda_text_memory_requirement", reject_staging
    )
    placements = place_instance(
        PlaceInstance(
            model_card=model,
            sharding=Sharding.Pipeline,
            instance_meta=InstanceMeta.MlxRing,
            min_nodes=1,
        ),
        topology,
        {},
        {local: create_node_memory(model.storage_size.in_bytes)},
        {local: create_node_network()},
        {local: [Backend.MlxCuda]},
        windows_node_ids={local},
        local_node_id=local,
        offload_policy=WindowsTextOffloadPolicy(enabled=True),
        host_available_bytes=0,
    )
    shard = next(
        iter(next(iter(placements.values())).shard_assignments.runner_to_shard.values())
    )
    assert shard.model_card.storage_size == model.storage_size
