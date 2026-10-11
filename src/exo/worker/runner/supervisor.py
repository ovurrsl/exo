import codecs
import contextlib
import signal
import sys
import time
from dataclasses import dataclass, field
from os import PathLike
from typing import Callable, Self

import anyio
from anyio import (
    AsyncFile,
    BrokenResourceError,
    CancelScope,
    ClosedResourceError,
)
from loguru import logger

from exo.shared.constants import EXO_RUNNER_STDERR_LOG, EXO_RUNNER_STDOUT_LOG
from exo.shared.types.chunks import ErrorChunk
from exo.shared.types.events import (
    ChunkGenerated,
    Event,
    RunnerStatusUpdated,
    TaskAcknowledged,
    TaskStatusUpdated,
)
from exo.shared.types.tasks import (
    CANCEL_ALL_TASKS,
    ImageEdits,
    ImageGeneration,
    Shutdown,
    Task,
    TaskId,
    TaskStatus,
    TextGeneration,
)
from exo.shared.types.worker.instances import BoundInstance
from exo.shared.types.worker.runners import (
    RunnerConnecting,
    RunnerFailed,
    RunnerIdle,
    RunnerLoading,
    RunnerRunning,
    RunnerShutdown,
    RunnerShuttingDown,
    RunnerStatus,
    RunnerWarmingUp,
)
from exo.shared.types.worker.shards import ShardMetadata
from exo.utils.async_process import AsyncProcess
from exo.utils.channels import MpReceiver, MpSender, Receiver, Sender, mp_channel
from exo.utils.fs import ensure_parent_directory_exists
from exo.utils.task_group import TaskGroup
from exo.worker.runner.bootstrap import RunnerTerminationError, entrypoint
from exo.worker.runner.diagnostics import (
    RunnerDiagnosticCollector,
    RunnerRingTransportError,
    RunnerUnknown,
)
from exo.worker.runner.windows_progress import WindowsProgressWatchdog

PREFILL_TIMEOUT_SECONDS = 60
DECODE_TIMEOUT_SECONDS = 5
RUNNER_WATCH_INTERVAL = 5.0


@dataclass(eq=False)
class RunnerStdioHandler:
    _stdout_rx: Receiver[bytes]
    _stderr_rx: Receiver[bytes]
    _stdout_log: AsyncFile[str]
    _stderr_log: AsyncFile[str]
    diagnostics: RunnerDiagnosticCollector = field(
        default_factory=RunnerDiagnosticCollector
    )

    _tg: TaskGroup = field(default_factory=TaskGroup, init=False)

    @classmethod
    async def create(
        cls,
        *,
        stdout_rx: Receiver[bytes],
        stderr_rx: Receiver[bytes],
        stdout_log_path: PathLike[str] = EXO_RUNNER_STDOUT_LOG,
        stderr_log_path: PathLike[str] = EXO_RUNNER_STDERR_LOG,
    ) -> Self:
        # these are append only logs used to gather data for log template mining
        #
        # TODO: in the future use [Drain3](https://github.com/logpai/Drain3)
        #       to mine these logs
        ensure_parent_directory_exists(stdout_log_path)
        ensure_parent_directory_exists(stderr_log_path)
        stdout_log = await anyio.open_file(stdout_log_path, "a")
        stderr_log = await anyio.open_file(stderr_log_path, "a")

        # instantiate and return
        self = cls(
            _stdout_rx=stdout_rx,
            _stderr_rx=stderr_rx,
            _stdout_log=stdout_log,
            _stderr_log=stderr_log,
        )
        return self

    async def run(self):
        try:
            async with self._tg as tg:
                tg.start_soon(  # pyright: ignore[reportUnknownArgumentType]
                    self._handle_runner_output,
                    self._stdout_rx,
                    self._stdout_log,
                    lambda line: logger.info(f"Runner stdout: {line}"),  # pyright: ignore[reportUnknownLambdaType]
                    lambda _: None,  # pyright: ignore[reportUnknownLambdaType]
                )
                tg.start_soon(  # pyright: ignore[reportUnknownArgumentType]
                    self._handle_runner_output,
                    self._stderr_rx,
                    self._stderr_log,
                    lambda line: logger.warning(f"Runner stderr: {line}"),  # pyright: ignore[reportUnknownLambdaType]
                    self.diagnostics.record_line,
                )
        finally:
            with CancelScope(shield=True):
                await self._stdout_log.aclose()
                await self._stderr_log.aclose()

    async def _handle_runner_output(
        self,
        rx: Receiver[bytes],
        logfile: AsyncFile[str],
        log_line: Callable[[str], None],
        record_diagnostic_line: Callable[[str], None],
    ):
        # The diagnostic collector is deliberately line-level for now. It records
        # bounded stderr context and known failure anchors; the supervisor
        # correlates those hints with the runner exit status before surfacing an
        # error.

        # not using TextReceiveStream because it doesn't do final=True handling on errors
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pending_line = ""

        async def handle_line(line: str):
            # preserve whitespace for later log-mining
            line = line.removesuffix("\r")
            if not line:
                return

            # Send to logger & error recovery task
            log_line(line)
            record_diagnostic_line(line)

        async def handle_text(text: str):
            nonlocal pending_line

            if not text:
                return

            await logfile.write(text)
            await logfile.flush()

            # newline buffering
            pending_line += text
            lines = pending_line.split("\n")
            pending_line = lines.pop()

            for line in lines:
                await handle_line(line)

        try:
            with rx:
                async for chunk in rx:
                    await handle_text(decoder.decode(chunk, final=False))
        except (ClosedResourceError, BrokenResourceError):
            logger.warning("Runner stdio stream closed before clean EOF")
        finally:
            with CancelScope(shield=True):
                await handle_text(decoder.decode(b"", final=True))
                await logfile.flush()

                if pending_line:
                    await handle_line(pending_line)
                    pending_line = ""


@dataclass(eq=False)
class RunnerSupervisor:
    shard_metadata: ShardMetadata
    bound_instance: BoundInstance
    runner_process: AsyncProcess
    _runner_stdio_handler: RunnerStdioHandler
    initialize_timeout: float
    _ev_recv: MpReceiver[Event | RunnerTerminationError]
    _task_sender: MpSender[Task]
    _event_sender: Sender[Event]
    _cancel_sender: MpSender[TaskId]
    _tg: TaskGroup = field(default_factory=TaskGroup, init=False)
    status: RunnerStatus = field(default_factory=RunnerIdle, init=False)
    pending: dict[TaskId, anyio.Event] = field(default_factory=dict, init=False)
    in_progress: dict[TaskId, Task] = field(default_factory=dict, init=False)
    completed: set[TaskId] = field(default_factory=set, init=False)
    cancelled: set[TaskId] = field(default_factory=set, init=False)
    _windows_progress: WindowsProgressWatchdog | None = field(default=None, init=False)
    _windows_stopping: bool = field(default=False, init=False)
    _shutdown_forwarded: anyio.Event = field(default_factory=anyio.Event, init=False)
    _windows_close_done: anyio.Event = field(default_factory=anyio.Event, init=False)
    _windows_close_succeeded: bool = field(default=False, init=False)
    _cancel_watch_runner: anyio.CancelScope = field(
        default_factory=anyio.CancelScope, init=False
    )

    @classmethod
    async def create(
        cls,
        *,
        bound_instance: BoundInstance,
        event_sender: Sender[Event],
        initialize_timeout: float = 400,
    ) -> Self:
        ev_send, ev_recv = mp_channel[Event | RunnerTerminationError]()
        task_sender, task_recv = mp_channel[Task]()
        cancel_sender, cancel_recv = mp_channel[TaskId]()

        runner_process = AsyncProcess(
            target=entrypoint,
            args=(
                bound_instance,
                ev_send,
                task_recv,
                cancel_recv,
                logger,
            ),
            daemon=True,
        )
        runner_stdio_handler = await RunnerStdioHandler.create(
            stdout_rx=runner_process.stdout, stderr_rx=runner_process.stderr
        )

        shard_metadata = bound_instance.bound_shard

        self = cls(
            bound_instance=bound_instance,
            shard_metadata=shard_metadata,
            runner_process=runner_process,
            _runner_stdio_handler=runner_stdio_handler,
            initialize_timeout=initialize_timeout,
            _ev_recv=ev_recv,
            _task_sender=task_sender,
            _cancel_sender=cancel_sender,
            _event_sender=event_sender,
        )

        if sys.platform == "win32":
            self._windows_progress = WindowsProgressWatchdog(
                time.monotonic(), initialize_timeout
            )

        return self

    async def run(self):
        try:
            async with self._tg as tg:
                # start the process itself & handle its stdout/stderr
                await tg.start(self.runner_process.run)
                tg.start_soon(self._runner_stdio_handler.run)

                tg.start_soon(self._watch_runner)
                tg.start_soon(self._forward_events)
        finally:
            logger.info("Runner supervisor shutting down")
            if not self._cancel_watch_runner.cancel_called:
                self._cancel_watch_runner.cancel()
            with contextlib.suppress(ClosedResourceError):
                self._ev_recv.close()
            with contextlib.suppress(ClosedResourceError):
                self._task_sender.close()
            with contextlib.suppress(ClosedResourceError):
                self._event_sender.close()
            with contextlib.suppress(ClosedResourceError):
                self._cancel_sender.send(CANCEL_ALL_TASKS)
            with contextlib.suppress(ClosedResourceError):
                self._cancel_sender.close()

            with anyio.CancelScope(shield=True):
                await self.runner_process.stop()
                logger.info(
                    f"Runner process successfully terminated: {self.runner_process.exitcode}"
                )

    def shutdown(self):
        self._tg.cancel_tasks()

    async def close_windows_runner(self, task: Shutdown | None = None) -> bool:
        """Request owned Windows worker exit before the enclosing group cancels."""
        if sys.platform != "win32":
            return True
        if self._windows_stopping:
            await self._windows_close_done.wait()
            return self._windows_close_succeeded
        self._windows_stopping = True
        try:
            with anyio.fail_after(8):
                with contextlib.suppress(ClosedResourceError):
                    await self._cancel_sender.send_async(CANCEL_ALL_TASKS)
                await self.start_task(
                    task
                    or Shutdown(
                        instance_id=self.bound_instance.instance.instance_id,
                        runner_id=self.bound_instance.bound_runner_id,
                    )
                )
                # The task-reader thread must also receive EOF. Leaving this
                # pipe open keeps its non-daemon thread alive after Shutdown.
                self._task_sender.close()
                code = await self.runner_process.wait()
                self._windows_close_succeeded = code == 0
                if code != 0:
                    logger.warning(f"Windows runner shutdown returned exit code {code}")
        except (TimeoutError, ClosedResourceError, BrokenResourceError, OSError):
            logger.warning(
                "Windows runner did not finish cooperative shutdown; stopping owned process"
            )
        finally:
            self._windows_close_done.set()
        return self._windows_close_succeeded

    async def start_task(self, task: Task):
        if task.task_id in self.pending:
            logger.warning(
                f"Skipping invalid task {task} as it has already been submitted"
            )
            return
        if task.task_id in self.completed:
            logger.warning(
                f"Skipping invalid task {task} as it has already been completed"
            )
            return
        logger.info(f"Starting task {task}")
        event = anyio.Event()
        self.pending[task.task_id] = event
        self.in_progress[task.task_id] = task
        if self._windows_progress is not None:
            self._windows_progress.progress(time.monotonic())
        try:
            await self._task_sender.send_async(task)
        except ClosedResourceError:
            self.in_progress.pop(task.task_id, None)
            logger.warning(f"Task {task} dropped, runner closed communication.")
            return
        await event.wait()
        if isinstance(task, Shutdown):
            # The worker cancels this supervisor when start_task returns.
            # Acknowledgement alone can drop the final cluster-state event.
            await self._shutdown_forwarded.wait()

    async def cancel_task(self, task_id: TaskId):
        if task_id in self.completed:
            logger.info(f"Unable to cancel {task_id} as it has been completed")
            self.cancelled.add(task_id)
            return
        self.cancelled.add(task_id)
        if self._windows_progress is not None and task_id in self.in_progress:
            self._windows_progress.cancel(task_id, time.monotonic())
        with anyio.move_on_after(0.5) as scope:
            try:
                await self._cancel_sender.send_async(task_id)
            except ClosedResourceError:
                # typically occurs when trying to shut down a failed instance
                logger.warning(
                    f"Cancelling task {task_id} failed, runner closed communication"
                )
        if scope.cancel_called:
            logger.error("RunnerSupervisor cancel pipe blocked")
            await self._check_runner(TimeoutError("cancel pipe blocked"))

    async def _forward_events(self):
        try:
            with self._ev_recv as events:
                async for event in events:
                    if self._windows_progress is not None:
                        self._windows_progress.progress(time.monotonic())
                    if isinstance(event, RunnerTerminationError):
                        # try to get exception if possible
                        await self._check_runner(event)
                        break
                    if isinstance(event, RunnerStatusUpdated):
                        self.status = event.runner_status
                    if isinstance(event, TaskAcknowledged):
                        self.pending.pop(event.task_id).set()
                        continue
                    if isinstance(event, TaskStatusUpdated) and (
                        event.task_status == TaskStatus.Complete
                        or (
                            self._windows_progress is not None
                            and event.task_status == TaskStatus.Cancelled
                        )
                    ):
                        # If a task has just been completed, we should be working on it.
                        assert isinstance(
                            self.status,
                            (
                                RunnerRunning,
                                RunnerWarmingUp,
                                RunnerLoading,
                                RunnerConnecting,
                                RunnerShuttingDown,
                            ),
                        )
                        self.in_progress.pop(event.task_id, None)
                        self.completed.add(event.task_id)
                        if self._windows_progress is not None:
                            self._windows_progress.completed(event.task_id)
                    await self._event_sender.send(event)
                    if isinstance(event, RunnerStatusUpdated) and isinstance(
                        event.runner_status, RunnerShutdown
                    ):
                        self._shutdown_forwarded.set()
        except (ClosedResourceError, BrokenResourceError):
            # this is the happy path shutdown - we don't need to spam log with it
            await self._check_runner()
        finally:
            for tid in self.pending:
                self.pending[tid].set()

    async def _watch_runner(self) -> None:
        with self._cancel_watch_runner:
            while True:
                await anyio.sleep(RUNNER_WATCH_INTERVAL)
                if not self.runner_process.is_alive():
                    await self._check_runner(RuntimeError("Runner found to be dead"))
                elif not self._windows_stopping and self._lost_its_peers():
                    await self._check_runner(
                        RuntimeError(
                            "Lost the connection to the instance's other runners"
                        )
                    )
                elif self._windows_progress is not None and not self._windows_stopping:
                    failure = self._windows_progress.failure(
                        time.monotonic(), self.status, bool(self.in_progress)
                    )
                    if failure is not None:
                        await self._check_runner(TimeoutError(failure))

    def _lost_its_peers(self) -> bool:
        return any(
            isinstance(diagnostic, RunnerRingTransportError)
            for diagnostic in self._runner_stdio_handler.diagnostics.diagnostics()
        )

    async def _check_runner(
        self, e: RunnerTerminationError | Exception | None = None
    ) -> None:
        # A Windows worker closes its event pipe before Python/native-library
        # finalization finishes. The cooperative closer owns that exit wait;
        # cancelling AsyncProcess here applies its shorter generic join grace.
        if self._windows_stopping and e is None and self.runner_process.is_alive():
            return
        if not self._cancel_watch_runner.cancel_called:
            self._cancel_watch_runner.cancel()
        logger.info("Checking runner's status")
        if self.runner_process.is_alive():
            logger.info("Runner was found to be alive, stopping process")
            with anyio.CancelScope(shield=True):
                await self.runner_process.stop()
        rc = self.runner_process.exitcode
        logger.info(f"Runner exited with exit code {rc}")

        # If exit code is 0 then the transient errors were recoverable, meaning we don't need runner diagnostics
        if rc == 0 and (
            e is None or self._windows_progress is None or self._windows_stopping
        ):
            return

        if isinstance(rc, int) and rc < 0:
            sig = -rc
            try:
                if (description := signal.strsignal(sig)) is not None:
                    cause = f"signal={sig} ({description})"
                else:
                    cause = f"signal={sig}"
            except Exception:
                cause = f"signal={sig}"
        else:
            cause: str = f"exitcode={rc}"

        if e is not None:
            # Record how runner shut down, try exception, resort to RunnerTerminationError fallback
            if isinstance(e, Exception):
                logger.opt(exception=e).error(f"Runner terminated with {cause}")
            else:
                cause = f"{cause}\nRunner error: {e}"
                logger.error(f"Runner terminated with {cause}")
        else:
            logger.error(f"Runner terminated with {cause}")

        diagnostics = [
            d
            for d in self._runner_stdio_handler.diagnostics.diagnostics()
            if not isinstance(d, RunnerUnknown)
        ]
        for task in self.in_progress.values():
            if isinstance(task, (TextGeneration, ImageGeneration, ImageEdits)):
                with anyio.CancelScope(shield=True):
                    await self._event_sender.send(
                        ChunkGenerated(
                            command_id=task.command_id,
                            chunk=ErrorChunk(
                                model=self.shard_metadata.model_card.model_id,
                                diagnostics=diagnostics,
                                error_message=(
                                    "Runner shutdown before completing command "
                                    f"({cause})"
                                ),
                            ),
                        )
                    )

        try:
            self.status = RunnerFailed(
                error_message=f"Terminated ({cause})", diagnostics=diagnostics
            )
            with anyio.CancelScope(shield=True):
                await self._event_sender.send(
                    RunnerStatusUpdated(
                        runner_id=self.bound_instance.bound_runner_id,
                        runner_status=self.status,
                    )
                )
        except (ClosedResourceError, BrokenResourceError):
            logger.warning(
                "Event sender already closed, unable to report runner failure"
            )
        self.shutdown()
