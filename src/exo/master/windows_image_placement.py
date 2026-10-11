"""Windows image qualification using existing identity and backend contracts."""

from collections.abc import Mapping, Sequence

from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.models.windows_image_budget import get_windows_image_budget
from exo.shared.types.backends import Backend
from exo.shared.types.common import NodeId
from exo.shared.types.memory import Memory
from exo.shared.types.profiling import NodeIdentity
from exo.shared.types.worker.instances import Instance, MlxRingInstance
from exo.shared.types.worker.shards import PipelineShardMetadata


def windows_nodes(identities: Mapping[NodeId, NodeIdentity]) -> set[NodeId]:
    return {
        node_id
        for node_id, identity in identities.items()
        if identity.os_version.casefold().startswith("windows")
    }


def cuda_image_memory_requirement(
    card: ModelCard,
    node_ids: Sequence[NodeId],
    node_backends: Mapping[NodeId, list[Backend]],
    windows_node_ids: set[NodeId],
) -> Memory | None:
    if (
        Backend.MlxCuda not in card.backends
        or not any(
            task in card.tasks
            for task in (ModelTask.TextToImage, ModelTask.ImageToImage)
        )
        or not any(Backend.MlxCuda in node_backends.get(node, []) for node in node_ids)
    ):
        return None
    budget = get_windows_image_budget(card.model_id)
    if budget is None or card.tasks != [ModelTask.TextToImage]:
        raise ValueError(
            "This CUDA image model requires separate release qualification"
        )
    if len(node_ids) != 1:
        raise ValueError(
            "Mixed or multi-node CUDA image pipelines require qualification"
        )
    if node_ids[0] not in windows_node_ids:
        raise ValueError("CUDA image inference requires a confirmed Windows node")
    if card.n_layers != budget.n_layers:
        raise ValueError("CUDA image model does not match the qualified layer layout")
    return budget.minimum_gpu_memory(0, budget.n_layers)


def cuda_image_instance_memory(
    instance: Instance,
    card: ModelCard,
    node_backends: Mapping[NodeId, list[Backend]],
    windows_node_ids: set[NodeId],
) -> Memory | None:
    assignments = instance.shard_assignments
    required = cuda_image_memory_requirement(
        card, list(assignments.node_to_runner), node_backends, windows_node_ids
    )
    if required is None:
        return None
    if (
        not isinstance(instance, MlxRingInstance)
        or len(assignments.runner_to_shard) != 1
    ):
        raise ValueError("CUDA image inference requires a single pipeline/ring runner")
    runner_id = next(iter(assignments.node_to_runner.values()))
    shard = assignments.runner_to_shard.get(runner_id)
    if (
        not isinstance(shard, PipelineShardMetadata)
        or shard.world_size != 1
        or shard.device_rank != 0
        or shard.start_layer != 0
        or shard.end_layer != card.n_layers
        or shard.n_layers != card.n_layers
        or shard.model_card != card
    ):
        raise ValueError("CUDA image instance does not match the full qualified shard")
    return required
