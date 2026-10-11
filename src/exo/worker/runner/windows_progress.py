"""Bounded progress monitoring for Windows runners, without wire-schema changes."""

from dataclasses import dataclass, field

from exo.shared.types.tasks import TaskId
from exo.shared.types.worker.runners import (
    RunnerConnecting,
    RunnerLoading,
    RunnerRunning,
    RunnerStatus,
    RunnerWarmingUp,
)


@dataclass
class WindowsProgressWatchdog:
    last_progress: float
    initialize_timeout: float
    generation_timeout: float = 300
    cancel_timeout: float = 15
    cancellation_deadlines: dict[TaskId, float] = field(default_factory=dict)

    def progress(self, now: float) -> None:
        self.last_progress = now

    def cancel(self, task_id: TaskId, now: float) -> None:
        self.cancellation_deadlines.setdefault(task_id, now + self.cancel_timeout)

    def completed(self, task_id: TaskId) -> None:
        self.cancellation_deadlines.pop(task_id, None)

    def failure(self, now: float, status: RunnerStatus, busy: bool) -> str | None:
        if isinstance(status, RunnerRunning):
            if any(
                now >= deadline for deadline in self.cancellation_deadlines.values()
            ):
                return "Runner did not complete cancellation within 15 seconds"
        else:
            self.cancellation_deadlines.clear()
        initializing = isinstance(
            status, (RunnerConnecting, RunnerLoading, RunnerWarmingUp)
        )
        if not initializing and not busy:
            return None
        timeout = self.initialize_timeout if initializing else self.generation_timeout
        if now - self.last_progress > timeout:
            return f"Runner made no progress for {timeout:g} seconds"
        return None
