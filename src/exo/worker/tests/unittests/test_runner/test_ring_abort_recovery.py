from typing import cast

import anyio
import pytest

import exo.worker.runner.supervisor as supervisor_module
from exo.shared.models.model_cards import ModelId
from exo.shared.types.common import NodeId
from exo.shared.types.events import Event, RunnerStatusUpdated
from exo.shared.types.tasks import Task, TaskId
from exo.shared.types.worker.instances import BoundInstance, InstanceId
from exo.shared.types.worker.runners import RunnerFailed, RunnerId
from exo.utils.async_process import AsyncProcess
from exo.utils.channels import channel, mp_channel
from exo.worker.runner.bootstrap import RunnerTerminationError
from exo.worker.runner.supervisor import RunnerStdioHandler, RunnerSupervisor
from exo.worker.tests.unittests.conftest import get_bound_mlx_ring_instance


class _StuckProcess:
    """A runner process that is alive but will never make progress again."""

    def __init__(self):
        rx1, _ = channel[bytes]()
        rx2, _ = channel[bytes]()
        self.stdout = rx1
        self.stderr = rx2
        self.exitcode: int | None = None

    def is_alive(self) -> bool:
        return self.exitcode is None

    async def stop(self) -> None:
        self.exitcode = -15


@pytest.mark.anyio
async def test_a_runner_whose_ring_aborted_is_stopped_and_reported_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(supervisor_module, "RUNNER_WATCH_INTERVAL", 0.01, raising=False)
    event_sender, event_receiver = channel[Event]()
    task_sender, _ = mp_channel[Task]()
    cancel_sender, _ = mp_channel[TaskId]()
    _, ev_recv = mp_channel[Event | RunnerTerminationError]()
    bound_instance: BoundInstance = get_bound_mlx_ring_instance(
        instance_id=InstanceId("instance-b"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=RunnerId("runner-b"),
        node_id=NodeId("node-b"),
    )
    stuck = _StuckProcess()
    proc = cast(AsyncProcess, cast(object, stuck))
    handler = await RunnerStdioHandler.create(
        stdout_rx=proc.stdout, stderr_rx=proc.stderr
    )
    supervisor = RunnerSupervisor(
        shard_metadata=bound_instance.bound_shard,
        bound_instance=bound_instance,
        runner_process=proc,
        _runner_stdio_handler=handler,
        initialize_timeout=400,
        _ev_recv=ev_recv,
        _task_sender=task_sender,
        _event_sender=event_sender,
        _cancel_sender=cancel_sender,
    )
    supervisor.shutdown = lambda: None
    for _ in range(10):
        handler.diagnostics.record_line(
            "[ring] Receiving from socket 51 failed with errno 54"
        )
    handler.diagnostics.record_line("[ring] Too many send/recv errors. Aborting...")

    with anyio.fail_after(2):
        await supervisor._watch_runner()  # pyright: ignore[reportPrivateUsage]
        status = await event_receiver.receive()

    assert not stuck.is_alive()
    assert isinstance(status, RunnerStatusUpdated)
    assert isinstance(status.runner_status, RunnerFailed)


@pytest.mark.anyio
@pytest.mark.parametrize("cooperative_stop", [False, True])
async def test_a_healthy_or_cooperatively_stopping_runner_is_left_alone(
    monkeypatch: pytest.MonkeyPatch, cooperative_stop: bool
) -> None:
    monkeypatch.setattr(supervisor_module, "RUNNER_WATCH_INTERVAL", 0.01, raising=False)
    event_sender, _ = channel[Event]()
    task_sender, _ = mp_channel[Task]()
    cancel_sender, _ = mp_channel[TaskId]()
    _, ev_recv = mp_channel[Event | RunnerTerminationError]()
    bound_instance: BoundInstance = get_bound_mlx_ring_instance(
        instance_id=InstanceId("instance-c"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=RunnerId("runner-c"),
        node_id=NodeId("node-c"),
    )
    healthy = _StuckProcess()
    proc = cast(AsyncProcess, cast(object, healthy))
    handler = await RunnerStdioHandler.create(
        stdout_rx=proc.stdout, stderr_rx=proc.stderr
    )
    supervisor = RunnerSupervisor(
        shard_metadata=bound_instance.bound_shard,
        bound_instance=bound_instance,
        runner_process=proc,
        _runner_stdio_handler=handler,
        initialize_timeout=400,
        _ev_recv=ev_recv,
        _task_sender=task_sender,
        _event_sender=event_sender,
        _cancel_sender=cancel_sender,
    )
    supervisor._windows_stopping = cooperative_stop  # pyright: ignore[reportPrivateUsage]
    handler.diagnostics.record_line(
        "[ring] Too many send/recv errors. Aborting..."
        if cooperative_stop
        else "some unrelated warning"
    )

    with anyio.move_on_after(0.1):
        await supervisor._watch_runner()  # pyright: ignore[reportPrivateUsage]

    assert healthy.is_alive()
