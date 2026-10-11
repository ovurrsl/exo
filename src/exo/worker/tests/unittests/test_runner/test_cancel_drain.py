"""The real runner must drain deferred MLX cancellation before announcing idle."""

import queue
from collections import deque
from types import SimpleNamespace
from typing import cast

import pytest

from exo.shared.types.chunks import GenerationChunk, TokenChunk
from exo.shared.types.events import Event, RunnerStatusUpdated, TaskStatusUpdated
from exo.shared.types.tasks import TaskId, TextGeneration
from exo.shared.types.worker.runner_response import (
    CancelledResponse,
    FinishedResponse,
    GenerationResponse,
)
from exo.shared.types.worker.runners import RunnerId, RunnerReady
from exo.utils.channels import MpSender
from exo.worker.engines.mlx.generator.batch_generate import ExoBatchGenerator
from exo.worker.runner.llm_inference.batch_generator import (
    BatchGenerator,
    GeneratorQueue,
)
from exo.worker.runner.runner import ExitCode, Runner, WorkItem
from exo.worker.tests.unittests.test_runner.test_batch_cancellation import (
    FakeMlxBatchGenerator,
    FakeResponse,
    engine,
    text_generation,
)


class TerminalMlx(FakeMlxBatchGenerator):
    steps = 0

    @property
    def retained_uids(self) -> list[int]:
        return list(self._generation_batch.uids)

    def next(self) -> tuple[list[object], list[FakeResponse]]:
        self.steps += 1
        batch = self._generation_batch
        done = [
            uid
            for uid, limit in zip(batch.uids, batch.max_tokens, strict=True)
            if limit == 0
        ]
        remaining = [
            (uid, limit)
            for uid, limit in zip(batch.uids, batch.max_tokens, strict=True)
            if uid not in done
        ]
        batch.uids = [uid for uid, _ in remaining]
        batch.max_tokens = [limit for _, limit in remaining]
        return [], [FakeResponse(uid=uid, finish_reason="length") for uid in done]


def bare_batch(
    monkeypatch: pytest.MonkeyPatch,
    tasks: list[TextGeneration],
    inner: ExoBatchGenerator,
) -> BatchGenerator:
    batch = object.__new__(BatchGenerator)
    monkeypatch.setattr(batch, "_gen", inner, raising=False)
    monkeypatch.setattr(batch, "_queue", deque[TextGeneration](), raising=False)
    monkeypatch.setattr(batch, "_maybe_queue", [], raising=False)
    monkeypatch.setattr(batch, "_all_tasks", {}, raising=False)
    monkeypatch.setattr(
        batch, "_cancelled_tasks", {t.task_id for t in tasks}, raising=False
    )
    active = {
        uid: (task, GeneratorQueue[GenerationResponse](), iter([]))
        for uid, task in enumerate(tasks)
    }
    monkeypatch.setattr(batch, "_active_tasks", active, raising=False)
    monkeypatch.setattr(batch, "device_rank", 0, raising=False)

    def no_agreement(_self: BatchGenerator) -> None:
        pass

    monkeypatch.setattr(BatchGenerator, "agree_on_tasks", no_agreement)
    return batch


@pytest.mark.parametrize("count", [1, 2])
def test_last_cancellations_are_drained_before_real_runner_becomes_ready(
    monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    tasks = [text_generation() for _ in range(count)]
    mlx = TerminalMlx(generating=list(range(count)), waiting=[])
    inner = engine(mlx)
    monkeypatch.setattr(
        inner,
        "_active_tasks",
        {
            uid: SimpleNamespace(task_params=task.task_params)
            for uid, task in enumerate(tasks)
        },
    )
    batch = bare_batch(monkeypatch, tasks, inner)
    observations: list[tuple[Event, list[int]]] = []

    class Collector:
        def send(self, event: Event) -> None:
            observations.append((event, mlx.retained_uids))

    runner = object.__new__(Runner)
    runner.generator = batch
    runner.current_status = RunnerReady()
    runner.runner_id = RunnerId()
    runner.seen = set[TaskId]()
    runner.active_tasks = {task.task_id: task for task in tasks[1:]}
    runner.event_sender = cast(MpSender[Event], cast(object, Collector()))
    monkeypatch.setattr(runner, "_work_queue", queue.Queue[WorkItem](), raising=False)
    monkeypatch.setattr(runner, "_prefill_server_port", None, raising=False)

    assert runner.handle_generation_tasks(tasks[0]) == ExitCode.AllTasksComplete
    terminal_observations = [
        retained
        for event, retained in observations
        if isinstance(event, TaskStatusUpdated)
        or (
            isinstance(event, RunnerStatusUpdated)
            and isinstance(event.runner_status, RunnerReady)
        )
    ]
    assert terminal_observations and all(
        not retained for retained in terminal_observations
    )
    assert not mlx.retained_uids
    assert mlx.steps == 2


def test_cancellation_drains_before_a_following_request_enters_prefill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task, following = text_generation(), text_generation()
    mlx = TerminalMlx(generating=[0], waiting=[])
    inner = engine(mlx)
    batch = bare_batch(monkeypatch, [task], inner)
    assert list(batch._apply_cancellations()) == [(task.task_id, CancelledResponse())]  # pyright: ignore[reportPrivateUsage]
    batch._queue.append(following)  # pyright: ignore[reportPrivateUsage]

    def start(_self: BatchGenerator, _task: TextGeneration) -> int:
        assert not mlx.retained_uids, "Old cancelled decode survives into new prefill"
        raise RuntimeError("prefill-reached")

    def send_error(
        _self: BatchGenerator, _task: TextGeneration, _error: Exception
    ) -> None:
        pass

    monkeypatch.setattr(BatchGenerator, "_start_task", start)
    monkeypatch.setattr(BatchGenerator, "_send_error", send_error)
    with pytest.raises(RuntimeError, match="prefill-reached"):
        batch.step()


def test_surviving_response_is_preserved_during_the_cancellation_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled, healthy = text_generation(), text_generation()
    mlx = TerminalMlx(generating=[0, 1], waiting=[])
    inner = engine(mlx)
    batch = bare_batch(monkeypatch, [cancelled, healthy], inner)
    monkeypatch.setattr(batch, "_cancelled_tasks", {cancelled.task_id})
    chunk = TokenChunk(
        model=healthy.task_params.model, text="ok", token_id=1, usage=None
    )
    active = {
        0: (cancelled, GeneratorQueue[GenerationResponse](), iter([])),
        1: (healthy, GeneratorQueue[GenerationResponse](), iter([chunk])),
    }
    monkeypatch.setattr(batch, "_active_tasks", active)

    def step(_self: ExoBatchGenerator) -> list[tuple[int, GenerationResponse]]:
        mlx.next()
        inner._finishing.clear()  # pyright: ignore[reportPrivateUsage]
        return [
            (
                1,
                GenerationResponse(
                    text="ok", token=1, finish_reason="stop", usage=None
                ),
            )
        ]

    monkeypatch.setattr(ExoBatchGenerator, "step", step)
    results = list(batch._apply_cancellations())  # pyright: ignore[reportPrivateUsage]
    expected: list[
        tuple[TaskId, GenerationChunk | FinishedResponse | CancelledResponse]
    ] = [
        (cancelled.task_id, CancelledResponse()),
        (healthy.task_id, chunk),
        (healthy.task_id, FinishedResponse()),
    ]
    assert results == expected
