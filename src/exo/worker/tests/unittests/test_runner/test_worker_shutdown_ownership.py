import sys
from typing import cast

import anyio
import pytest

from exo.shared.models.model_cards import ModelId
from exo.shared.types.commands import ForwarderCommand, ForwarderDownloadCommand
from exo.shared.types.common import NodeId
from exo.shared.types.events import Event, IndexedEvent, TaskCreated, TaskStatusUpdated
from exo.shared.types.tasks import Shutdown, Task, TaskId, TaskStatus
from exo.shared.types.worker.instances import InstanceId
from exo.shared.types.worker.runners import RunnerId, RunnerReady
from exo.utils.channels import channel
from exo.worker.main import Worker
from exo.worker.runner.supervisor import RunnerSupervisor
from exo.worker.tests.unittests.conftest import get_bound_mlx_ring_instance


@pytest.mark.parametrize("platform", ["win32", "darwin"])
@pytest.mark.parametrize("finishes", [True, False])
async def test_shutdown_ownership_until_windows_finalization(
    monkeypatch: pytest.MonkeyPatch, platform: str, finishes: bool
) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    node_id = NodeId("closing-node")
    runner_id = RunnerId("closing-runner")
    bound = get_bound_mlx_ring_instance(
        instance_id=InstanceId("closing-instance"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=runner_id,
        node_id=node_id,
    )
    entered = anyio.Event()
    finalized = anyio.Event()
    cancelled = anyio.Event()

    class ClosingRunner:
        bound_instance = bound
        status = RunnerReady()
        completed: set[TaskId] = set()
        in_progress: dict[TaskId, Task] = {}

        async def start_task(self, task: Task) -> None:
            assert platform == "darwin" and isinstance(task, Shutdown)
            entered.set()
            await finalized.wait()
            if not finishes:
                raise TimeoutError

        async def close_windows_runner(self, task: Shutdown | None = None) -> bool:
            assert platform == "win32" and task is not None
            assert task.runner_id == runner_id
            entered.set()
            await finalized.wait()
            return finishes

        def shutdown(self) -> None:
            assert finalized.is_set()
            cancelled.set()

    incoming, receiver = channel[IndexedEvent]()
    outgoing, event_receiver = channel[Event]()
    commands, command_receiver = channel[ForwarderCommand]()
    downloads, download_receiver = channel[ForwarderDownloadCommand]()
    worker = Worker(
        node_id,
        event_receiver=receiver,
        event_sender=outgoing,
        command_sender=commands,
        download_command_sender=downloads,
        api_port=52415,
    )
    worker.runners[runner_id] = cast(RunnerSupervisor, cast(object, ClosingRunner()))
    try:
        with anyio.fail_after(3):
            async with anyio.create_task_group() as group:
                group.start_soon(worker.plan_step)
                await entered.wait()
                created = await event_receiver.receive()
                assert isinstance(created, TaskCreated)
                assert (runner_id in worker.runners) == (platform == "win32")
                if platform == "win32":
                    await worker.stop_windows_admission()
                    assert runner_id in worker.runners
                finalized.set()
                if not finishes:
                    event = await event_receiver.receive()
                    assert isinstance(event, TaskStatusUpdated)
                    assert event.task_id == created.task_id
                    assert event.task_status == TaskStatus.TimedOut
                await cancelled.wait()
                assert runner_id not in worker.runners
                group.cancel_scope.cancel()
    finally:
        incoming.close()
        outgoing.close()
        commands.close()
        downloads.close()
        await receiver.aclose()
        await event_receiver.aclose()
        await command_receiver.aclose()
        await download_receiver.aclose()
