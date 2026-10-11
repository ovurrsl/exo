import pytest

from exo.master.cuda_placement import failed_cuda_instance_events
from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.common import CommandId, ModelId, NodeId
from exo.shared.types.events import InstanceDeleted, TaskStatusUpdated
from exo.shared.types.memory import Memory
from exo.shared.types.state import State
from exo.shared.types.tasks import TaskId, TaskStatus, TextGeneration
from exo.shared.types.text_generation import TextGenerationTaskParams
from exo.shared.types.worker.instances import InstanceId, MlxRingInstance
from exo.shared.types.worker.runners import RunnerFailed, RunnerId, ShardAssignments
from exo.shared.types.worker.shards import PipelineShardMetadata


@pytest.fixture
def failed_state() -> State:
    nodes = [NodeId(), NodeId()]
    runners = [RunnerId(), RunnerId()]
    card = ModelCard(
        model_id=ModelId("test/model"),
        storage_size=Memory.from_mb(1),
        n_layers=2,
        hidden_size=4,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxCuda, Backend.MlxMetal],
    )
    assignments = ShardAssignments(
        model_id=card.model_id,
        node_to_runner=dict(zip(nodes, runners, strict=True)),
        runner_to_shard={
            runner: PipelineShardMetadata(
                model_card=card,
                device_rank=rank,
                world_size=2,
                start_layer=rank,
                end_layer=rank + 1,
                n_layers=2,
            )
            for rank, runner in enumerate(runners)
        },
    )
    instance = MlxRingInstance(
        instance_id=InstanceId(),
        shard_assignments=assignments,
        hosts_by_node={},
        ephemeral_port=50000,
    )
    task = TextGeneration(
        task_id=TaskId(),
        command_id=CommandId(),
        instance_id=instance.instance_id,
        task_status=TaskStatus.Running,
        task_params=TextGenerationTaskParams(model=card.model_id, input=[]),
    )
    return State(
        instances={instance.instance_id: instance},
        runners={runners[1]: RunnerFailed(error_message="peer lost", diagnostics=[])},
        tasks={task.task_id: task},
        node_backends={nodes[0]: [Backend.MlxCuda]},
    )


def test_failure_on_mac_rank_cancels_whole_cuda_instance(failed_state: State) -> None:
    events = failed_cuda_instance_events(failed_state)
    assert isinstance(events[0], TaskStatusUpdated)
    assert events[0].task_status == TaskStatus.Cancelled
    assert isinstance(events[1], InstanceDeleted)
    assert events[1].instance_id in failed_state.instances


def test_mac_only_recovery_behavior_is_preserved(failed_state: State) -> None:
    assert (
        failed_cuda_instance_events(
            failed_state.model_copy(update={"node_backends": {}})
        )
        == []
    )
