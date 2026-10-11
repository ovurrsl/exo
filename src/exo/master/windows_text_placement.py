"""Local Windows text staging admission without treating host RAM as VRAM."""

import sys
from collections.abc import Mapping, Sequence

import psutil

from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.common import NodeId
from exo.shared.types.memory import Memory
from exo.shared.types.worker.instances import Instance, MlxRingInstance
from exo.shared.types.worker.shards import PipelineShardMetadata
from exo.utils.windows_text_offload_config import (
    WINDOWS_TEXT_PHYSICAL_HEADROOM_BYTES,
    WindowsTextOffloadPolicy,
    read_windows_text_offload_policy,
)


def local_windows_text_offload_policy() -> WindowsTextOffloadPolicy | None:
    if sys.platform != "win32":
        return None
    try:
        return read_windows_text_offload_policy()
    except (ValueError, MemoryError):
        return None


def is_windows_text_offload_card(card: ModelCard) -> bool:
    dense_bases = {
        "Qwen3 0.6B",
        "Qwen3 1.7B",
        "Qwen3 4B",
        "Qwen3 8B",
        "Qwen3 14B",
        "Qwen3 32B",
    }
    return (
        Backend.MlxCuda in card.backends
        and card.tasks == [ModelTask.TextGeneration]
        and card.vision is None
        and card.quantization == "4bit"
        and card.base_model in dense_bases
    )


def _has_audited_catalogue_geometry(card: ModelCard) -> bool:
    # Only audited stock cards provide the uniform decoder / quantized head
    # assumptions needed by the catalogue estimate. A family label alone cannot
    # certify a custom model's vocabulary, head dtype or largest decoder.
    profiles = {
        "mlx-community/Qwen3-0.6B-4bit": ("Qwen3 0.6B", 28, 1024),
        "mlx-community/Qwen3-32B-4bit": ("Qwen3 32B", 64, 5120),
    }
    return profiles.get(str(card.model_id)) == (
        card.base_model,
        card.n_layers,
        card.hidden_size,
    ) and card.num_key_value_heads in (None, 8)


def cuda_text_memory_requirement(
    card: ModelCard,
    node_ids: Sequence[NodeId],
    node_backends: Mapping[NodeId, list[Backend]],
    windows_node_ids: set[NodeId],
    *,
    offload_policy: WindowsTextOffloadPolicy | None = None,
    local_node_id: NodeId | None = None,
    host_available_bytes: int | None = None,
) -> Memory | None:
    if (
        offload_policy is None
        or not offload_policy.enabled
        or local_node_id is None
        or list(node_ids) != [local_node_id]
        or local_node_id not in windows_node_ids
        or Backend.MlxCuda not in node_backends.get(local_node_id, [])
        or not is_windows_text_offload_card(card)
        or not _has_audited_catalogue_geometry(card)
    ):
        return None
    offload_policy.validate()
    storage = card.storage_size.in_bytes
    decoder = (storage + card.n_layers - 1) // card.n_layers
    # Affine 4-bit head with group32 and FP32 scales/biases is an upper bound
    # for the audited group32/group64 stock head, including BF16 storage.
    head = (151936 * card.hidden_size * 3 + 3) // 4
    norm = card.hidden_size * 4
    largest = max(decoder, head)
    if host_available_bytes is None:
        host_available_bytes = int(psutil.virtual_memory().available)
    required_host = storage + 6 * largest + offload_policy.host_reserve_bytes
    if (
        storage <= 0
        or (
            offload_policy.host_limit_bytes
            and storage > offload_policy.host_limit_bytes
        )
        or required_host > host_available_bytes
    ):
        raise ValueError("Windows text offload host memory budget is insufficient")
    # Use FP32 KV as the conservative supported storage width. The runtime uses
    # the actual tensors. Its padded cache and two-layer growth scratch are
    # separate from the runtime reserve already deducted from reported VRAM.
    layer_kv = 2 * 8 * 128 * (offload_policy.max_context_tokens + 255) * 4
    required = (
        max(3 * head, head + norm + 3 * decoder)
        + layer_kv * (card.n_layers + 2)
        + WINDOWS_TEXT_PHYSICAL_HEADROOM_BYTES
    )
    if offload_policy.stage_limit_bytes and decoder > offload_policy.stage_limit_bytes:
        raise ValueError("Windows text offload stage memory budget is insufficient")
    # Reported CUDA capacity already excludes the 2.5 GiB runtime reserve;
    # the explicit padded KV budget above must still be included.
    return Memory.from_bytes(required)


def cuda_text_instance_memory(
    instance: Instance,
    card: ModelCard,
    node_backends: Mapping[NodeId, list[Backend]],
    windows_node_ids: set[NodeId],
    *,
    offload_policy: WindowsTextOffloadPolicy | None = None,
    local_node_id: NodeId | None = None,
    host_available_bytes: int | None = None,
) -> Memory | None:
    assignments = instance.shard_assignments
    required = cuda_text_memory_requirement(
        card,
        list(assignments.node_to_runner),
        node_backends,
        windows_node_ids,
        offload_policy=offload_policy,
        local_node_id=local_node_id,
        host_available_bytes=host_available_bytes,
    )
    if required is None:
        return None
    if (
        not isinstance(instance, MlxRingInstance)
        or len(assignments.runner_to_shard) != 1
    ):
        raise ValueError("Windows text offload requires a single pipeline/ring runner")
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
        raise ValueError("Windows text offload requires a full qualified shard")
    return required
