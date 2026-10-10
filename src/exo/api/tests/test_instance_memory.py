from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from exo.api.main import API
from exo.api.types import CreateInstanceParams
from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.common import ModelId, NodeId
from exo.shared.types.memory import Memory
from exo.shared.types.profiling import MemoryUsage
from exo.shared.types.state import State
from exo.shared.types.worker.instances import InstanceId, MlxRingInstance
from exo.shared.types.worker.runners import RunnerId, ShardAssignments
from exo.shared.types.worker.shards import PipelineShardMetadata


@pytest.mark.parametrize("shortfall", [1, 20_000_000, 0])
async def test_create_instance_reports_exact_capacity_without_rounding_admission(
    monkeypatch: pytest.MonkeyPatch, shortfall: int
) -> None:
    required = 8_964_930_516
    available = required - shortfall
    card = ModelCard(
        model_id=ModelId("test/rounding-boundary"),
        storage_size=Memory.from_bytes(required),
        n_layers=1,
        hidden_size=1,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxCuda],
    )
    monkeypatch.setattr(ModelCard, "load", AsyncMock(return_value=card))
    node, runner = NodeId(), RunnerId()
    instance = MlxRingInstance(
        instance_id=InstanceId(),
        shard_assignments=ShardAssignments(
            model_id=card.model_id,
            node_to_runner={node: runner},
            runner_to_shard={
                runner: PipelineShardMetadata(
                    model_card=card,
                    device_rank=0,
                    world_size=1,
                    start_layer=0,
                    end_layer=1,
                    n_layers=1,
                )
            },
        ),
        hosts_by_node={node: []},
        ephemeral_port=1234,
    )
    api = object.__new__(API)
    api.state = State(
        node_memory={
            node: MemoryUsage.from_bytes(
                ram_total=12 * 1024**3,
                ram_available=available,
                swap_total=0,
                swap_available=0,
            )
        }
    )
    sender = AsyncMock()
    monkeypatch.setattr(api, "_send", sender)
    payload = CreateInstanceParams(instance=instance)
    if shortfall:
        assert f"{card.storage_size.in_gb:.1f}" == f"{available / 1024**3:.1f}"
        with pytest.raises(HTTPException) as caught:
            await api.create_instance(payload)
        assert caught.value.status_code == 400
        assert "8,964,930,516 bytes" in caught.value.detail
        assert f"{available:,} bytes" in caught.value.detail
        assert f"{shortfall:,} bytes" in caught.value.detail
        assert "GiB" in caught.value.detail
        assert "Shortfall:" in caught.value.detail
        sender.assert_not_awaited()
    else:
        response = await api.create_instance(payload)
        assert response.model_card == card
        sender.assert_awaited_once()
