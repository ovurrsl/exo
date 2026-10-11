import sys
from pathlib import Path
from typing import cast

import anyio
import pytest

from exo.shared.models.model_cards import ModelId
from exo.shared.types.chunks import ErrorChunk
from exo.shared.types.common import CommandId, NodeId
from exo.shared.types.events import (
    ChunkGenerated,
    Event,
    RunnerStatusUpdated,
    TaskAcknowledged,
    TaskStatusUpdated,
)
from exo.shared.types.tasks import Shutdown, Task, TaskId, TaskStatus, TextGeneration
from exo.shared.types.text_generation import (
    InputMessage,
    InputMessageContent,
    TextGenerationTaskParams,
)
from exo.shared.types.worker.instances import BoundInstance, InstanceId
from exo.shared.types.worker.runners import (
    RunnerFailed,
    RunnerId,
    RunnerReady,
    RunnerShutdown,
    RunnerShuttingDown,
)
from exo.utils.async_process import AsyncProcess
from exo.utils.channels import channel, mp_channel
from exo.worker.runner.bootstrap import RunnerTerminationError
from exo.worker.runner.supervisor import RunnerStdioHandler, RunnerSupervisor
from exo.worker.runner.windows_progress import WindowsProgressWatchdog
from exo.worker.tests.unittests.conftest import get_bound_mlx_ring_instance


class _DeadProcess:
    def __init__(self):
        rx1, _ = channel[bytes]()
        rx2, _ = channel[bytes]()
        self.stdout = rx1
        self.stderr = rx2

    exitcode = -6

    def is_alive(self) -> bool:
        return False


@pytest.mark.anyio
async def test_check_runner_emits_error_chunk_for_inflight_text_generation() -> None:
    event_sender, event_receiver = channel[Event]()
    task_sender, _ = mp_channel[Task]()
    cancel_sender, _ = mp_channel[TaskId]()
    _, ev_recv = mp_channel[Event | RunnerTerminationError]()

    bound_instance: BoundInstance = get_bound_mlx_ring_instance(
        instance_id=InstanceId("instance-a"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=RunnerId("runner-a"),
        node_id=NodeId("node-a"),
    )

    proc = cast(AsyncProcess, cast(object, _DeadProcess()))
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

    command_id = CommandId("cmd-a")
    task = TextGeneration(
        task_id=TaskId("task-a"),
        instance_id=bound_instance.instance.instance_id,
        command_id=command_id,
        task_params=TextGenerationTaskParams(
            model=bound_instance.bound_shard.model_card.model_id,
            input=[InputMessage(role="user", content=InputMessageContent("hi"))],
            stream=True,
        ),
    )
    supervisor.in_progress[task.task_id] = task
    supervisor.shutdown = lambda: None

    await supervisor._check_runner(RuntimeError("boom"))  # pyright: ignore[reportPrivateUsage]

    got_chunk = await event_receiver.receive()
    got_status = await event_receiver.receive()

    assert isinstance(got_chunk, ChunkGenerated)
    assert got_chunk.command_id == command_id
    assert isinstance(got_chunk.chunk, ErrorChunk)
    assert "Runner shutdown before completing command" in got_chunk.chunk.error_message

    assert isinstance(got_status, RunnerStatusUpdated)
    assert isinstance(got_status.runner_status, RunnerFailed)

    event_sender.close()
    with anyio.move_on_after(0.1):
        await event_receiver.aclose()


async def test_cooperative_close_does_not_terminate_alive_process_after_event_eof() -> (
    None
):
    class FinalizingProcess:
        exitcode: int | None = None

        def __init__(self) -> None:
            _tx1, self.stdout = channel[bytes]()
            _tx2, self.stderr = channel[bytes]()
            self.stopped = False

        def is_alive(self) -> bool:
            return True

        async def stop(self) -> None:
            self.stopped = True

    process = FinalizingProcess()
    typed_process = cast(AsyncProcess, cast(object, process))
    event_sender, event_receiver = channel[Event]()
    task_sender, _task_receiver = mp_channel[Task]()
    cancel_sender, _cancel_receiver = mp_channel[TaskId]()
    _event_sender, events = mp_channel[Event | RunnerTerminationError]()
    bound = get_bound_mlx_ring_instance(
        instance_id=InstanceId("finalizing-instance"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=RunnerId("finalizing-runner"),
        node_id=NodeId("finalizing-node"),
    )
    handler = await RunnerStdioHandler.create(
        stdout_rx=typed_process.stdout, stderr_rx=typed_process.stderr
    )
    supervisor = RunnerSupervisor(
        shard_metadata=bound.bound_shard,
        bound_instance=bound,
        runner_process=typed_process,
        _runner_stdio_handler=handler,
        initialize_timeout=400,
        _ev_recv=events,
        _task_sender=task_sender,
        _event_sender=event_sender,
        _cancel_sender=cancel_sender,
    )
    supervisor.status = RunnerReady()
    supervisor._windows_stopping = True  # pyright: ignore[reportPrivateUsage]
    supervisor.shutdown = lambda: None
    # Event-pipe EOF precedes CPU PyTorch's interpreter/DLL finalization.
    await supervisor._check_runner()  # pyright: ignore[reportPrivateUsage]
    assert not process.stopped
    assert isinstance(supervisor.status, RunnerReady)
    event_sender.close()
    await event_receiver.aclose()
    task_sender.close()
    cancel_sender.close()
    events.close()


@pytest.mark.parametrize("windows_watchdog", [False, True])
async def test_shutdown_waits_for_final_status_delivery(
    tmp_path: Path, windows_watchdog: bool
) -> None:
    event_sender, event_receiver = channel[Event](0)
    task_sender, task_receiver = mp_channel[Task]()
    cancel_sender, cancel_receiver = mp_channel[TaskId]()
    runner_events, events = mp_channel[Event | RunnerTerminationError]()
    bound = get_bound_mlx_ring_instance(
        instance_id=InstanceId("shutdown-instance"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=RunnerId("shutdown-runner"),
        node_id=NodeId("shutdown-node"),
    )
    process = cast(AsyncProcess, cast(object, _DeadProcess()))
    handler = await RunnerStdioHandler.create(
        stdout_rx=process.stdout,
        stderr_rx=process.stderr,
        stdout_log_path=tmp_path / "stdout.log",
        stderr_log_path=tmp_path / "stderr.log",
    )
    supervisor = RunnerSupervisor(
        shard_metadata=bound.bound_shard,
        bound_instance=bound,
        runner_process=process,
        _runner_stdio_handler=handler,
        initialize_timeout=400,
        _ev_recv=events,
        _task_sender=task_sender,
        _event_sender=event_sender,
        _cancel_sender=cancel_sender,
    )
    if windows_watchdog:
        supervisor._windows_progress = WindowsProgressWatchdog(0, 400)  # pyright: ignore[reportPrivateUsage]
    task = Shutdown(
        instance_id=bound.instance.instance_id,
        runner_id=bound.bound_runner_id,
    )
    finished = anyio.Event()

    async def request_shutdown() -> None:
        await supervisor.start_task(task)
        finished.set()

    try:
        with anyio.fail_after(3):
            async with anyio.create_task_group() as group:
                group.start_soon(supervisor._forward_events)  # pyright: ignore[reportPrivateUsage]
                group.start_soon(request_shutdown)
                assert await task_receiver.receive_async() == task
                await runner_events.send_async(
                    RunnerStatusUpdated(
                        runner_id=bound.bound_runner_id,
                        runner_status=RunnerShuttingDown(),
                    )
                )
                await event_receiver.receive()
                await runner_events.send_async(TaskAcknowledged(task_id=task.task_id))
                await runner_events.send_async(
                    TaskStatusUpdated(
                        task_id=task.task_id, task_status=TaskStatus.Complete
                    )
                )
                await event_receiver.receive()
                await anyio.wait_all_tasks_blocked()
                # Worker cancellation after this return must not drop the
                # final status, even after acknowledgement and task completion.
                assert not finished.is_set()
                await runner_events.send_async(
                    RunnerStatusUpdated(
                        runner_id=bound.bound_runner_id,
                        runner_status=RunnerShutdown(),
                    )
                )
                await anyio.wait_all_tasks_blocked()
                # The downstream channel is unbuffered: local status alone
                # does not establish that the event reached the router.
                assert not finished.is_set()
                final_event = await event_receiver.receive()
                assert isinstance(final_event, RunnerStatusUpdated)
                assert isinstance(final_event.runner_status, RunnerShutdown)
                await finished.wait()
                group.cancel_scope.cancel()
    finally:
        runner_events.close()
        events.close()
        task_sender.close()
        task_receiver.close()
        cancel_sender.close()
        cancel_receiver.close()
        event_sender.close()
        await event_receiver.aclose()
        await handler._stdout_log.aclose()  # pyright: ignore[reportPrivateUsage]
        await handler._stderr_log.aclose()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows cooperative closer")
@pytest.mark.parametrize("finishes", [True, False])
async def test_repeated_cooperative_close_waits_for_process_finalization(
    tmp_path: Path,
    finishes: bool,
) -> None:
    class FinalizingProcess:
        exitcode: int | None = None

        def __init__(self) -> None:
            _stdout_sender, self.stdout = channel[bytes]()
            _stderr_sender, self.stderr = channel[bytes]()
            self.waiting = anyio.Event()
            self.finished = anyio.Event()

        def is_alive(self) -> bool:
            return self.exitcode is None

        async def wait(self) -> int:
            self.waiting.set()
            await self.finished.wait()
            self.exitcode = 0
            return 0

    process = FinalizingProcess()
    typed_process = cast(AsyncProcess, cast(object, process))
    event_sender, event_receiver = channel[Event]()
    task_sender, task_receiver = mp_channel[Task]()
    cancel_sender, cancel_receiver = mp_channel[TaskId]()
    runner_events, events = mp_channel[Event | RunnerTerminationError]()
    bound = get_bound_mlx_ring_instance(
        instance_id=InstanceId("cooperative-instance"),
        model_id=ModelId("mlx-community/Llama-3.2-1B-Instruct-4bit"),
        runner_id=RunnerId("cooperative-runner"),
        node_id=NodeId("cooperative-node"),
    )
    handler = await RunnerStdioHandler.create(
        stdout_rx=typed_process.stdout,
        stderr_rx=typed_process.stderr,
        stdout_log_path=tmp_path / "stdout.log",
        stderr_log_path=tmp_path / "stderr.log",
    )
    supervisor = RunnerSupervisor(
        shard_metadata=bound.bound_shard,
        bound_instance=bound,
        runner_process=typed_process,
        _runner_stdio_handler=handler,
        initialize_timeout=400,
        _ev_recv=events,
        _task_sender=task_sender,
        _event_sender=event_sender,
        _cancel_sender=cancel_sender,
    )
    received_tasks: list[Task] = []

    async def acknowledge(task: Task) -> None:
        received_tasks.append(task)

    supervisor.start_task = acknowledge
    repeated_close_done = anyio.Event()
    close_results: list[bool] = []

    async def first_close() -> None:
        close_results.append(await supervisor.close_windows_runner())

    async def repeated_close() -> None:
        close_results.append(await supervisor.close_windows_runner())
        repeated_close_done.set()

    try:
        with anyio.fail_after(12):
            async with anyio.create_task_group() as group:
                group.start_soon(first_close)
                await process.waiting.wait()
                group.start_soon(repeated_close)
                await anyio.wait_all_tasks_blocked()
                assert not repeated_close_done.is_set()
                if finishes:
                    process.finished.set()
                await repeated_close_done.wait()
        assert close_results == [finishes, finishes]
        assert len(received_tasks) == 1
        assert isinstance(received_tasks[0], Shutdown)
    finally:
        runner_events.close()
        events.close()
        task_sender.close()
        task_receiver.close()
        cancel_sender.close()
        cancel_receiver.close()
        event_sender.close()
        await event_receiver.aclose()
        await handler._stdout_log.aclose()  # pyright: ignore[reportPrivateUsage]
        await handler._stderr_log.aclose()  # pyright: ignore[reportPrivateUsage]
