"""An owned Windows close must drain distributed ranks before router teardown."""

from typing import cast

import anyio
import pytest

from exo.main import Node
from exo.shared.models.model_cards import ModelId
from exo.shared.types.commands import (
    DeleteInstance,
    ForwarderCommand,
    ForwarderDownloadCommand,
)
from exo.shared.types.common import NodeId
from exo.shared.types.events import Event, IndexedEvent
from exo.shared.types.state import State
from exo.shared.types.worker.instances import InstanceId
from exo.shared.types.worker.runners import RunnerId, RunnerReady
from exo.utils.channels import channel
from exo.utils.task_group import TaskGroup
from exo.worker.main import Worker
from exo.worker.runner.supervisor import RunnerSupervisor
from exo.worker.tests.unittests.conftest import get_bound_mlx_ring_instance


@pytest.mark.parametrize("commands_open", [True, False])
async def test_windows_node_close_deletes_owned_instance_and_waits_for_peer(
    commands_open: bool,
) -> None:
    node_id = NodeId("closing-windows")
    runner_id = RunnerId("local-runner")
    bound = get_bound_mlx_ring_instance(
        instance_id=InstanceId("owned-instance"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=runner_id,
        node_id=node_id,
    )
    unrelated = get_bound_mlx_ring_instance(
        instance_id=InstanceId("unrelated-instance"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=RunnerId("unrelated-runner"),
        node_id=NodeId("unrelated-node"),
    )
    deletion_seen = anyio.Event()
    local_closed = anyio.Event()

    class ClosingRunner:
        bound_instance = bound

        async def close_windows_runner(self) -> bool:
            if commands_open:
                await deletion_seen.wait()
            local_closed.set()
            return True

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
    worker.state = State(
        instances={
            bound.instance.instance_id: bound.instance,
            unrelated.instance.instance_id: unrelated.instance,
        },
        runners={
            runner_id: RunnerReady(),
            RunnerId("other_runner"): RunnerReady(),
            RunnerId("unrelated-runner"): RunnerReady(),
        },
    )
    node = Node.__new__(Node)
    node.api = None
    node.worker = worker
    node._tg = TaskGroup()  # pyright: ignore[reportPrivateUsage]
    if not commands_open:
        commands.close()
    try:
        with anyio.fail_after(3):
            async with node._tg as group:  # pyright: ignore[reportPrivateUsage]
                group.start_soon(node._shutdown_windows)  # pyright: ignore[reportPrivateUsage]
                if not commands_open:
                    await anyio.sleep_forever()
                command = await command_receiver.receive()
                assert isinstance(command.command, DeleteInstance)
                assert command.command.instance_id == bound.instance.instance_id
                assert worker.windows_draining
                deletion_seen.set()
                await local_closed.wait()
                worker.state = worker.state.model_copy(
                    update={
                        "instances": {
                            unrelated.instance.instance_id: unrelated.instance
                        },
                        "runners": {
                            RunnerId("other_runner"): RunnerReady(),
                            RunnerId("unrelated-runner"): RunnerReady(),
                        },
                    }
                )
                await anyio.wait_all_tasks_blocked()
                assert not node._tg.cancel_called()  # pyright: ignore[reportPrivateUsage]
                worker.state = worker.state.model_copy(
                    update={
                        "runners": {RunnerId("unrelated-runner"): RunnerReady()},
                    }
                )
                await anyio.sleep_forever()
        assert node._tg.cancel_called()  # pyright: ignore[reportPrivateUsage]
        assert local_closed.is_set()
        assert unrelated.instance.instance_id in worker.state.instances
    finally:
        incoming.close()
        outgoing.close()
        commands.close()
        downloads.close()
        await receiver.aclose()
        await event_receiver.aclose()
        await command_receiver.aclose()
        await download_receiver.aclose()
