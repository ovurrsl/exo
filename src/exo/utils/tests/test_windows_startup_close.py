"""Windows startup/close regressions with real cancellation and owned cleanup."""

import time
import types
from typing import Literal, cast

import anyio
import pytest

import exo.main as node_module
from exo.api.main import API
from exo.download.coordinator import DownloadCoordinator
from exo.main import Node
from exo.master.main import Master
from exo.routing.event_router import EventRouter
from exo.routing.router import Router
from exo.shared.election import ElectionResult
from exo.shared.types.common import NodeId, SessionId
from exo.shared.types.worker.runners import RunnerId
from exo.utils.channels import channel
from exo.utils.task_group import TaskGroup
from exo.worker.main import Worker
from exo.worker.runner.supervisor import RunnerSupervisor


async def test_stalled_admission_reaches_global_shutdown_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admission_started = anyio.Event()

    class StalledWorker:
        runners: dict[RunnerId, RunnerSupervisor] = {}

        async def stop_windows_admission(self) -> None:
            admission_started.set()
            await anyio.sleep_forever()

    def short_deadline(_seconds: float) -> anyio.CancelScope:
        return anyio.move_on_after(0.05)

    monkeypatch.setattr(
        node_module, "anyio", types.SimpleNamespace(move_on_after=short_deadline)
    )
    node = Node.__new__(Node)
    node.api = None
    node.worker = cast(Worker, cast(object, StalledWorker()))
    node._tg = TaskGroup()  # pyright: ignore[reportPrivateUsage]
    started = time.monotonic()
    async with node._tg:  # pyright: ignore[reportPrivateUsage]
        await node._shutdown_windows()  # pyright: ignore[reportPrivateUsage]
    assert admission_started.is_set()
    assert time.monotonic() - started < 1
    assert node._tg.cancel_called()  # pyright: ignore[reportPrivateUsage]


async def _election_close_race(
    stage: Literal["master", "coordinator"], monkeypatch: pytest.MonkeyPatch
) -> None:
    shutdown_started, finish_shutdown, election_finished = (
        anyio.Event(),
        anyio.Event(),
        anyio.Event(),
    )

    class PausedApi:
        paused = True
        resets = 0

        def unpause(self, _clock: int) -> None:
            self.paused = False

        def reset(self, clock: int, _receiver: object) -> None:
            self.resets += 1
            self.unpause(clock)

    class StalledComponent:
        async def shutdown(self) -> None:
            shutdown_started.set()
            await finish_shutdown.wait()

        async def run(self) -> None:
            await anyio.sleep_forever()

    class ElectionRouter:
        def shutdown(self) -> None:
            pass

        def sender(self, _topic: object = None) -> object:
            return object()

        def receiver(self, _topic: object = None) -> object:
            return object()

        async def run(self) -> None:
            await anyio.sleep_forever()

    router = ElectionRouter()
    replacements: list[StalledComponent] = []

    def new_event_router(*_args: object, **_kwargs: object) -> EventRouter:
        return cast(EventRouter, cast(object, router))

    def new_coordinator(*_args: object, **_kwargs: object) -> DownloadCoordinator:
        component = StalledComponent()
        replacements.append(component)
        return cast(DownloadCoordinator, cast(object, component))

    def new_downloader(*_args: object, **_kwargs: object) -> object:
        return object()

    monkeypatch.setattr(node_module, "EventRouter", new_event_router)
    monkeypatch.setattr(node_module, "DownloadCoordinator", new_coordinator)
    monkeypatch.setattr(node_module, "exo_shard_downloader", new_downloader)
    sender, receiver = channel[ElectionResult]()
    api, component = PausedApi(), StalledComponent()
    node = Node.__new__(Node)
    node.node_id = NodeId("local")
    node.api = cast(API, cast(object, api))
    node.worker = None
    node.master = cast(Master, cast(object, component)) if stage == "master" else None
    node.download_coordinator = (
        cast(DownloadCoordinator, cast(object, component))
        if stage == "coordinator"
        else None
    )
    node.router = cast(Router, cast(object, router))
    node.event_router = cast(EventRouter, cast(object, router))
    node.offline = True
    node.election_result_receiver = receiver
    node._windows_shutdown_started = False  # pyright: ignore[reportPrivateUsage]
    node._tg = TaskGroup()  # pyright: ignore[reportPrivateUsage]

    async def elect() -> None:
        try:
            await node._elect_loop()  # pyright: ignore[reportPrivateUsage]
        finally:
            election_finished.set()

    with anyio.fail_after(1):
        async with node._tg:  # pyright: ignore[reportPrivateUsage]
            node._tg.start_soon(elect)  # pyright: ignore[reportPrivateUsage]
            await sender.send(
                ElectionResult(
                    session_id=SessionId(
                        master_node_id=NodeId("peer"), election_clock=1
                    ),
                    won_clock=1,
                    is_new_master=stage == "coordinator",
                )
            )
            await shutdown_started.wait()
            node._windows_shutdown_started = True  # pyright: ignore[reportPrivateUsage]
            finish_shutdown.set()
            await sender.aclose()
            await election_finished.wait()
            assert api.paused, "Election resumed API admission during Windows close"
            assert api.resets == 0, "Election reset the API while closing"
            assert not replacements, "Election recreated the coordinator while closing"
            node._tg.cancel_tasks()  # pyright: ignore[reportPrivateUsage]


async def test_demoting_master_during_close_keeps_api_paused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _election_close_race("master", monkeypatch)


async def test_api_only_coordinator_shutdown_during_close_does_not_reset_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _election_close_race("coordinator", monkeypatch)
