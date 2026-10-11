from exo.shared.types.tasks import TaskId
from exo.shared.types.worker.runners import RunnerLoading, RunnerReady, RunnerRunning
from exo.worker.runner.windows_progress import WindowsProgressWatchdog


def test_idle_is_not_timed_out_but_busy_stalled_runner_is() -> None:
    monitor = WindowsProgressWatchdog(last_progress=0, initialize_timeout=400)
    assert monitor.failure(1000, RunnerReady(), False) is None
    assert monitor.failure(301, RunnerRunning(), True) is not None
    monitor.progress(302)
    assert monitor.failure(400, RunnerRunning(), True) is None


def test_loading_progress_extends_initialization_deadline() -> None:
    monitor = WindowsProgressWatchdog(last_progress=0, initialize_timeout=400)
    assert monitor.failure(399, RunnerLoading(), True) is None
    monitor.progress(398)
    assert monitor.failure(700, RunnerLoading(), True) is None
    assert monitor.failure(799, RunnerLoading(), True) is not None


def test_other_progress_cannot_hide_stalled_cancellation() -> None:
    monitor = WindowsProgressWatchdog(last_progress=0, initialize_timeout=400)
    task_id = TaskId()
    monitor.cancel(task_id, 1)
    monitor.progress(15)
    assert monitor.failure(16, RunnerRunning(), True) is not None
    monitor.completed(task_id)
    assert monitor.failure(17, RunnerRunning(), True) is None


def test_repeated_cancel_does_not_extend_deadline_and_ready_clears_it() -> None:
    monitor = WindowsProgressWatchdog(last_progress=0, initialize_timeout=400)
    task_id = TaskId()
    monitor.cancel(task_id, 1)
    monitor.cancel(task_id, 14)
    assert monitor.failure(16, RunnerRunning(), True) is not None
    assert monitor.failure(17, RunnerReady(), False) is None
    assert not monitor.cancellation_deadlines
