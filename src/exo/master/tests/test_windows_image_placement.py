import tomllib
from pathlib import Path

import pytest

from exo.master.placement import place_instance
from exo.master.tests.conftest import create_node_memory, create_node_network
from exo.master.windows_image_placement import (
    cuda_image_instance_memory,
    cuda_image_memory_requirement,
    windows_nodes,
)
from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.models.windows_image_budget import get_windows_image_budget
from exo.shared.topology import Topology
from exo.shared.types.backends import Backend
from exo.shared.types.commands import PlaceInstance
from exo.shared.types.common import ModelId, NodeId
from exo.shared.types.memory import Memory
from exo.shared.types.profiling import NodeIdentity
from exo.shared.types.worker.instances import InstanceMeta, MlxRingInstance
from exo.shared.types.worker.shards import Sharding


@pytest.fixture
def schnell() -> ModelCard:
    path = Path("resources/image_model_cards/exolabs--FLUX.1-schnell-4bit.toml")
    return ModelCard.model_validate(tomllib.loads(path.read_text())).model_copy(
        update={"backends": [Backend.MlxMetal, Backend.MlxCuda]}
    )


def placed_image(card: ModelCard, *, cuda: bool, available: int) -> MlxRingInstance:
    node = NodeId()
    topology = Topology()
    topology.add_node(node)
    placement = place_instance(
        PlaceInstance(
            model_card=card,
            sharding=Sharding.Pipeline,
            instance_meta=InstanceMeta.MlxRing,
            min_nodes=1,
        ),
        topology,
        {},
        {node: create_node_memory(available)},
        {node: create_node_network()},
        {node: [Backend.MlxCuda if cuda else Backend.MlxMetal]},
        windows_node_ids={node} if cuda else set(),
    )
    instance = next(iter(placement.values()))
    assert isinstance(instance, MlxRingInstance)
    return instance


def test_single_windows_stage_fits_without_changing_wire_card(
    schnell: ModelCard,
) -> None:
    instance = placed_image(schnell, cuda=True, available=8 * 1024**3)
    shard = next(iter(instance.shard_assignments.runner_to_shard.values()))
    assert shard.model_card == schnell
    assert shard.model_card.storage_size.in_bytes == 15_470_210_592
    assert (shard.start_layer, shard.end_layer, shard.world_size) == (0, 57, 1)


def test_cuda_capacity_is_per_node_and_does_not_use_disk_estimate(
    schnell: ModelCard,
) -> None:
    budget = get_windows_image_budget(schnell.model_id)
    assert budget is not None
    with pytest.raises(ValueError, match="sufficient memory"):
        placed_image(
            schnell,
            cuda=True,
            available=budget.minimum_gpu_memory(0, budget.n_layers).in_bytes - 1,
        )


def test_mac_image_memory_path_retains_original_requirement(schnell: ModelCard) -> None:
    with pytest.raises(ValueError, match="sufficient memory"):
        placed_image(schnell, cuda=False, available=8 * 1024**3)
    instance = placed_image(schnell, cuda=False, available=16 * 1024**3)
    assert (
        next(iter(instance.shard_assignments.runner_to_shard.values())).model_card
        == schnell
    )


def test_unknown_os_and_mixed_cuda_image_are_not_qualified(schnell: ModelCard) -> None:
    win, mac = NodeId(), NodeId()
    backends = {win: [Backend.MlxCuda], mac: [Backend.MlxMetal]}
    with pytest.raises(ValueError, match="confirmed Windows"):
        cuda_image_memory_requirement(schnell, [win], backends, set())
    with pytest.raises(ValueError, match="multi-node"):
        cuda_image_memory_requirement(schnell, [win, mac], backends, {win})
    assert windows_nodes(
        {
            win: NodeIdentity(os_version="Windows 11"),
            mac: NodeIdentity(os_version="macOS 27"),
        }
    ) == {win}


def test_unadvertised_cuda_card_retains_legacy_path(schnell: ModelCard) -> None:
    node = NodeId()
    assert (
        cuda_image_memory_requirement(
            schnell.model_copy(update={"backends": [Backend.MlxMetal]}),
            [node],
            {node: [Backend.MlxCuda]},
            {node},
        )
        is None
    )


@pytest.mark.parametrize("editing", [False, True])
def test_other_cuda_image_families_and_editing_remain_unqualified(
    schnell: ModelCard, editing: bool
) -> None:
    node = NodeId()
    card = schnell.model_copy(
        update={"tasks": [ModelTask.ImageToImage]}
        if editing
        else {"model_id": ModelId("unqualified/image-family")}
    )
    with pytest.raises(ValueError, match="separate release qualification"):
        cuda_image_memory_requirement(card, [node], {node: [Backend.MlxCuda]}, {node})


def test_direct_create_cannot_bypass_full_shard_layout(schnell: ModelCard) -> None:
    instance = placed_image(schnell, cuda=True, available=8 * 1024**3)
    node, runner = next(iter(instance.shard_assignments.node_to_runner.items()))
    assert cuda_image_instance_memory(
        instance, schnell, {node: [Backend.MlxCuda]}, {node}
    ) == Memory.from_bytes(6_693_214_336)
    shard = instance.shard_assignments.runner_to_shard[runner]
    instance = instance.model_copy(
        update={
            "shard_assignments": instance.shard_assignments.model_copy(
                update={
                    "runner_to_shard": {
                        runner: shard.model_copy(update={"end_layer": 28})
                    }
                }
            )
        }
    )
    with pytest.raises(ValueError, match="full qualified shard"):
        cuda_image_instance_memory(instance, schnell, {node: [Backend.MlxCuda]}, {node})
