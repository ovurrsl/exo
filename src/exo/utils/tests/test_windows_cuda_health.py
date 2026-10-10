import subprocess
import sys
import time
import types
from contextlib import suppress
from unittest import mock

import anyio
import psutil
import pytest

from exo.shared.types.backends import Backend
from exo.utils import windows_cuda_health as health
from exo.utils.channels import channel
from exo.utils.info_gatherer import info_gatherer as info_module
from exo.utils.info_gatherer.info_gatherer import NodeBackends
from exo.utils.windows_cuda_probe import SUCCESS_EXIT_CODE, SUCCESS_MARKER


@pytest.fixture(autouse=True)
def fresh_probe_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        health,
        "_probe_cache",
        health._WindowsCudaHealthCache(health._probe_windows_cuda_once),  # pyright: ignore[reportPrivateUsage]
    )


def test_marker_without_clean_exit_does_not_advertise_cuda():
    result = health._validate_exit(  # pyright: ignore[reportPrivateUsage]
        0xC0000409, f"{SUCCESS_MARKER}0.32.3\n", "driver shutting down", "kernel"
    )
    assert not result.available
    assert "driver shutting down" in result.reason


def test_clean_exit_and_marker_identify_the_loaded_runtime():
    result = health._validate_exit(  # pyright: ignore[reportPrivateUsage]
        SUCCESS_EXIT_CODE, f"{SUCCESS_MARKER}0.32.3\n", "", "ring"
    )
    assert result.available
    assert result.mlx_version == "0.32.3"


def test_frozen_probe_uses_executable_inline_dispatch():
    with mock.patch.object(sys, "executable", "C:/Program Files/exo/exo.exe"):
        command = health._probe_command("kernel")  # pyright: ignore[reportPrivateUsage]
    assert command[:2] == ["C:/Program Files/exo/exo.exe", "-c"]
    assert "run_probe('kernel')" in command[2]


def test_kernel_timeout_is_a_capability_failure():
    with mock.patch.object(
        subprocess, "Popen", side_effect=subprocess.TimeoutExpired("probe", 0.01)
    ):
        result = health._run_kernel({}, 0.01)  # pyright: ignore[reportPrivateUsage]
    assert not result.available
    assert "timed out" in result.reason


def test_timeout_kills_child_and_bounds_cleanup():
    class StuckProcess:
        returncode = 0
        args = ["probe"]
        pid = 0

        def __init__(self) -> None:
            self.killed = False
            self.timeouts: list[float | None] = []

        def poll(self) -> int | None:
            return None

        def kill(self) -> None:
            self.killed = True

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            self.timeouts.append(timeout)
            time.sleep(timeout or 0)
            raise subprocess.TimeoutExpired("probe", timeout or 0)

    child = StuckProcess()
    with (
        mock.patch.object(subprocess, "Popen", return_value=child),
        mock.patch.object(psutil, "Process", side_effect=psutil.NoSuchProcess(0)),
    ):
        result = health._run_kernel({}, 0.01)  # pyright: ignore[reportPrivateUsage]
    assert not result.available
    assert child.killed
    assert child.timeouts[-1] == 0.5
    assert all(
        timeout is not None and timeout <= 0.01 for timeout in child.timeouts[:-1]
    )


def test_failed_kernel_never_starts_ring_ranks():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(
            health,
            "_run_kernel",
            return_value=health.WindowsCudaHealth(False, "bad CUDA"),
        ),
        mock.patch.object(health, "_run_ring", side_effect=AssertionError),
    ):
        result = health.probe_windows_cuda()
    assert not result.available


@pytest.mark.skipif(sys.platform != "win32", reason="Windows retained process handle")
def test_probe_cleanup_uses_owned_popen_handle_when_reopening_parent_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    original_kill = psutil.Process.kill

    def deny_parent(process_to_kill: psutil.Process) -> None:
        if process_to_kill.pid == process.pid:
            raise psutil.AccessDenied(process.pid)
        original_kill(process_to_kill)

    monkeypatch.setattr(psutil.Process, "kill", deny_parent)
    try:
        health._stop_processes([process])  # pyright: ignore[reportPrivateUsage]
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=3)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows retained process handle")
def test_parent_probe_is_reaped_even_when_descendant_discovery_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    def denied(_pid: int) -> psutil.Process:
        raise psutil.AccessDenied(process.pid)

    monkeypatch.setattr(psutil, "Process", denied)
    try:
        with pytest.raises(psutil.AccessDenied):
            health._stop_processes([process])  # pyright: ignore[reportPrivateUsage]
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=3)


def test_runtime_replacement_during_probe_is_rejected():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(
            health,
            "_run_kernel",
            return_value=health.WindowsCudaHealth(True, "ok", "1"),
        ),
        mock.patch.object(
            health, "_run_ring", return_value=health.WindowsCudaHealth(True, "ok", "2")
        ),
    ):
        result = health.probe_windows_cuda()
    assert not result.available
    assert "changed" in result.reason


def test_failed_health_is_retried_after_thirty_seconds_then_success_is_kept():
    now = [0.0]
    calls: list[int] = []

    def probe() -> health.WindowsCudaHealth:
        calls.append(1)
        return health.WindowsCudaHealth(len(calls) > 1, "probe", "tested")

    cache = health._WindowsCudaHealthCache(probe, lambda: now[0])  # pyright: ignore[reportPrivateUsage]
    assert not cache.read().available
    now[0] = 29.9
    assert not cache.read().available
    assert len(calls) == 1
    now[0] = 30
    assert cache.read().available
    now[0] = 1000
    assert cache.read().available
    assert len(calls) == 2


def test_failure_retry_delay_begins_when_the_slow_probe_finishes():
    now = [0.0]
    calls: list[int] = []

    def probe() -> health.WindowsCudaHealth:
        calls.append(1)
        now[0] += 15
        return health.WindowsCudaHealth(False, "timeout")

    cache = health._WindowsCudaHealthCache(probe, lambda: now[0])  # pyright: ignore[reportPrivateUsage]
    assert not cache.read().available
    now[0] = 44.9
    assert not cache.read().available
    assert len(calls) == 1
    now[0] = 45
    assert not cache.read().available
    assert len(calls) == 2


def test_public_health_keeps_success_and_bounds_each_probe_stage():
    timeouts: list[float] = []

    def probe_stage(
        _environment: dict[str, str], *, timeout: float
    ) -> health.WindowsCudaHealth:
        timeouts.append(timeout)
        return health.WindowsCudaHealth(True, "verified", "tested")

    with (
        mock.patch.object(health, "sys", types.SimpleNamespace(platform="win32")),
        mock.patch.object(health, "_run_kernel", probe_stage),
        mock.patch.object(health, "_run_ring", probe_stage),
    ):
        assert health.probe_windows_cuda().available
        assert health.probe_windows_cuda().available
    assert timeouts == [15, 15]


async def test_backend_monitor_retries_failure_and_publishes_the_recovered_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def gather() -> NodeBackends:
        calls.append(1)
        return NodeBackends(backends=[Backend.MlxCuda] if len(calls) > 1 else [])

    monkeypatch.setattr(NodeBackends, "gather", gather)
    sender, receiver = channel[info_module.GatheredInfo]()
    monitor = info_module.InfoGatherer(sender)
    with anyio.fail_after(1):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(monitor._monitor_windows_backends, 0.01)  # pyright: ignore[reportPrivateUsage]
            first = await receiver.receive()
            second = await receiver.receive()
            assert isinstance(first, NodeBackends) and first.backends == []
            assert isinstance(second, NodeBackends)
            assert second.backends == [Backend.MlxCuda]
            await anyio.sleep(0.04)
            assert len(calls) >= 3
            with anyio.move_on_after(0.02) as silence:
                await receiver.receive()
                raise AssertionError("An unchanged healthy backend was republished")
            assert silence.cancel_called
            tasks.cancel_scope.cancel()
    await sender.aclose()
    await receiver.aclose()


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows child cleanup")
@pytest.mark.parametrize("stage", ["kernel", "ring"])
async def test_startup_close_cancels_and_reaps_a_blocked_health_child(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    children: list[subprocess.Popen[str]] = []
    descendants: list[psutil.Process] = []
    real_popen = subprocess.Popen[str]

    def spawn(command: list[str], **_options: object) -> subprocess.Popen[str]:
        # Keep Popen/pipe/cleanup behavior real; only replace expensive CUDA work.
        process = real_popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        children.append(process)
        return process

    async def gather() -> None:
        await NodeBackends.gather()

    def probe_command(_stage: str) -> list[str]:
        # Exercise an interpreter launcher and an additional owned descendant.
        return [
            sys.executable,
            "-c",
            "import subprocess, sys, time; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
            "time.sleep(30)",
        ]

    def healthy_kernel(
        _environment: dict[str, str], *, timeout: float
    ) -> health.WindowsCudaHealth:
        return health.WindowsCudaHealth(True, "kernel", "tested")

    if stage == "ring":
        monkeypatch.setattr(
            health,
            "_run_kernel",
            healthy_kernel,
        )

    monkeypatch.setattr(
        health,
        "_probe_command",
        probe_command,
    )
    monkeypatch.setattr(subprocess, "Popen", spawn)
    started = time.monotonic()
    try:
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(gather)
            with anyio.fail_after(3):
                while len(children) != (1 if stage == "kernel" else 2):
                    await anyio.sleep(0.01)
                while True:
                    trees = [
                        psutil.Process(child.pid).children(recursive=True)
                        for child in children
                    ]
                    if all(len(tree) >= 2 for tree in trees):
                        descendants = [process for tree in trees for process in tree]
                        break
                    await anyio.sleep(0.01)
            started = time.monotonic()
            tasks.cancel_scope.cancel()
        assert time.monotonic() - started < 3, (
            "Startup close waited for the health timeout"
        )
        assert all(child.poll() is not None for child in children), (
            "Owned health child survived cancellation"
        )
        assert all(not process.is_running() for process in descendants), (
            "Owned interpreter descendant survived cancellation"
        )
    finally:
        health._stop_processes(children)  # pyright: ignore[reportPrivateUsage]
        # Reap the deliberately created descendants even against the broken code.
        for process in descendants:
            with suppress(psutil.NoSuchProcess):
                process.kill()
        _ = psutil.wait_procs(descendants, timeout=1)


def test_child_rejects_multiple_devices_before_importing_cuda():
    from exo.utils.windows_cuda_probe import run_probe

    nvml = types.ModuleType("pynvml")
    calls: list[str] = []

    def initialize() -> None:
        calls.append("initialize")

    def shutdown() -> None:
        calls.append("shutdown")

    def device_count() -> int:
        return 2

    for name, implementation in (
        ("nvmlInit", initialize),
        ("nvmlShutdown", shutdown),
        ("nvmlDeviceGetCount", device_count),
    ):
        setattr(nvml, name, implementation)
    with (
        mock.patch.dict(sys.modules, {"pynvml": nvml, "mlx": None}),
        pytest.raises(RuntimeError, match="Exactly one NVIDIA GPU"),
    ):
        run_probe("kernel")
    assert calls == ["initialize", "shutdown"]


async def test_windows_backends_require_real_runtime_health():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch(
            "exo.utils.info_gatherer.info_gatherer.probe_windows_cuda",
            return_value=health.WindowsCudaHealth(False, "kernel failed"),
        ),
    ):
        result = await NodeBackends.gather()
    assert result.backends == []


async def test_windows_advertises_only_the_verified_cuda_backend():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch(
            "exo.utils.info_gatherer.info_gatherer.probe_windows_cuda",
            return_value=health.WindowsCudaHealth(True, "verified", "0.32.3"),
        ),
    ):
        result = await NodeBackends.gather()
    assert result.backends == [Backend.MlxCuda]
