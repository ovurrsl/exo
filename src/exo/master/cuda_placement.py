"""Additional admission and recovery rules for instances containing CUDA ranks."""

from exo.master.placement import get_transition_events
from exo.shared.types.backends import Backend
from exo.shared.types.events import Event
from exo.shared.types.state import State
from exo.shared.types.worker.runners import RunnerFailed


def failed_cuda_instance_events(state: State) -> list[Event]:
    """Remove every rank of a CUDA instance after one rank fails.

    The existing deletion transition also cancels in-flight tasks and removes
    instance links. Mac-only instances retain their existing recovery behavior.
    """
    targets = dict(state.instances)
    for instance_id, instance in state.instances.items():
        assignments = instance.shard_assignments
        contains_cuda = any(
            Backend.MlxCuda in state.node_backends.get(node_id, [])
            for node_id in assignments.node_to_runner
        )
        if contains_cuda and any(
            isinstance(state.runners.get(runner_id), RunnerFailed)
            for runner_id in assignments.runner_to_shard
        ):
            del targets[instance_id]
    return list(get_transition_events(state.instances, targets, state.tasks))
