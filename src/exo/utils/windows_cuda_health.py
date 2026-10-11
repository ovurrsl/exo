"""Bounded, frozen-safe checks before Windows advertises a CUDA backend."""

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import final

import psutil
from anyio import NoEventLoopError, from_thread

from exo.utils.windows_cuda_probe import SUCCESS_EXIT_CODE, SUCCESS_MARKER


@final
@dataclass(frozen=True)
class WindowsCudaHealth:
    available: bool
    reason: str
    mlx_version: str | None = None


def _check_probe_cancelled() -> None:
    # The synchronous CLI/hardware gates have no owning AnyIO task.
    with suppress(NoEventLoopError):
        from_thread.check_cancelled()


def _communicate_probe(
    process: subprocess.Popen[str], timeout: float
) -> tuple[str, str]:
    deadline = time.monotonic() + timeout
    while True:
        _check_probe_cancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout)
        try:
            return process.communicate(timeout=min(0.1, remaining))
        except subprocess.TimeoutExpired:
            continue


def _probe_command(stage: str) -> list[str]:
    # PyInstaller's executable supports -c through exo.__main__, whereas -m
    # would start the application. No temporary executable scripts are needed.
    code = f"from exo.utils.windows_cuda_probe import run_probe; run_probe({stage!r})"
    return [sys.executable, "-c", code]


def _validate_exit(
    return_code: int, stdout: str, stderr: str, stage: str
) -> WindowsCudaHealth:
    versions = [
        line.removeprefix(SUCCESS_MARKER)
        for line in stdout.splitlines()
        if line.startswith(SUCCESS_MARKER)
    ]
    if return_code != SUCCESS_EXIT_CODE or len(versions) != 1:
        detail = (stderr or stdout).strip()[-1000:]
        return WindowsCudaHealth(
            False, f"MLX {stage} probe failed (exit {return_code}): {detail}"
        )
    return WindowsCudaHealth(
        True, "CUDA kernel, ring and process exit verified", versions[0]
    )


def _run_kernel(environment: dict[str, str], timeout: float) -> WindowsCudaHealth:
    process: subprocess.Popen[str] | None = None
    try:
        _check_probe_cancelled()
        process = subprocess.Popen(
            _probe_command("kernel"),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        stdout, stderr = _communicate_probe(process, timeout)
        return _validate_exit(process.returncode, stdout, stderr, "kernel")
    except subprocess.TimeoutExpired:
        return WindowsCudaHealth(False, "MLX CUDA kernel probe timed out")
    except OSError as error:
        return WindowsCudaHealth(False, f"Cannot start MLX CUDA kernel probe: {error}")
    finally:
        if process is not None:
            _stop_processes([process])


def _stop_processes(processes: list[subprocess.Popen[str]]) -> None:
    owned: list[psutil.Process] = []
    try:
        if sys.platform == "win32":
            # uv's venv python.exe is a launcher. Killing only its Popen PID leaves
            # the interpreter alive, retaining CUDA/ports and the captured pipes.
            # Capture descendants while the launcher still owns them and terminate
            # the deepest children first. psutil checks each Process creation time
            # before killing, so a recycled PID cannot select an unrelated process.
            for process in processes:
                if process.poll() is None:
                    with suppress(psutil.NoSuchProcess):
                        parent = psutil.Process(process.pid)
                        owned.extend(reversed(parent.children(recursive=True)))
                        # The original Popen handle owns the parent. Reopening it
                        # through psutil can fail while Windows is tearing it down.
            for descendant in owned:
                with suppress(psutil.NoSuchProcess):
                    descendant.kill()
            _ = psutil.wait_procs(owned, timeout=0.5)
    finally:
        # Reap retained parent handles even when descendant inspection fails.
        for process in processes:
            if process.poll() is None:
                with suppress(OSError):
                    process.kill()
        for process in processes:
            with suppress(subprocess.TimeoutExpired, OSError):
                _ = process.communicate(timeout=0.5)


def _run_ring(environment: dict[str, str], timeout: float) -> WindowsCudaHealth:
    processes: list[subprocess.Popen[str]] = []
    deadline = time.monotonic() + timeout
    with TemporaryDirectory(prefix="exo-cuda-health-") as temporary:
        # Keep both sockets bound until the hostfile is complete, then release
        # them immediately before launching the local ranks.
        with socket.socket() as first, socket.socket() as second:
            first.bind(("127.0.0.1", 0))
            second.bind(("127.0.0.1", 0))
            addresses = [
                [f"127.0.0.1:{first.getsockname()[1]}"],
                [f"127.0.0.1:{second.getsockname()[1]}"],
            ]
            hostfile = Path(temporary) / "hosts.json"
            _ = hostfile.write_text(json.dumps(addresses), encoding="utf-8")
        try:
            for rank in range(2):
                _check_probe_cancelled()
                rank_environment = environment | {
                    "MLX_RANK": str(rank),
                    "MLX_HOSTFILE": str(hostfile),
                    "MLX_RING_VERBOSE": "0",
                }
                processes.append(
                    subprocess.Popen(
                        _probe_command("ring"),
                        env=rank_environment,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        creationflags=(
                            subprocess.CREATE_NO_WINDOW
                            if sys.platform == "win32"
                            else 0
                        ),
                    )
                )
            health = WindowsCudaHealth(False, "No ring ranks completed")
            for process in processes:
                stdout, stderr = _communicate_probe(
                    process, timeout=max(0.01, deadline - time.monotonic())
                )
                health = _validate_exit(process.returncode, stdout, stderr, "ring")
                if not health.available:
                    return health
            return health
        except subprocess.TimeoutExpired:
            return WindowsCudaHealth(False, "MLX CPU-stream ring probe timed out")
        except OSError as error:
            return WindowsCudaHealth(False, f"Cannot start MLX ring probe: {error}")
        finally:
            _stop_processes(processes)


def _probe_windows_cuda_once() -> WindowsCudaHealth:
    if sys.platform != "win32":
        return WindowsCudaHealth(
            False, "Windows CUDA health is only checked on Windows"
        )
    environment = dict(os.environ)
    for name in (
        "MLX_RANK",
        "MLX_HOSTFILE",
        "MLX_JACCL_COORDINATOR",
        "MLX_MPI_HOSTFILE",
    ):
        environment.pop(name, None)
    kernel = _run_kernel(environment, timeout=15)
    if not kernel.available:
        return kernel
    try:
        ring = _run_ring(environment, timeout=15)
    except OSError as error:
        return WindowsCudaHealth(False, f"Cannot prepare MLX ring probe: {error}")
    if ring.available and ring.mlx_version != kernel.mlx_version:
        return WindowsCudaHealth(
            False, "The installed MLX runtime changed during probing"
        )
    return ring


@final
class _WindowsCudaHealthCache:
    def __init__(
        self,
        probe: Callable[[], WindowsCudaHealth],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._probe = probe
        self._clock = clock
        self._lock = Lock()
        self._result: WindowsCudaHealth | None = None
        self._retry_after = 0.0

    def read(self) -> WindowsCudaHealth:
        # Concurrent info requests must not launch duplicate CUDA/ring children.
        _check_probe_cancelled()
        while not self._lock.acquire(timeout=0.1):
            _check_probe_cancelled()
        try:
            _check_probe_cancelled()
            result = self._result
            if result is None or (
                not result.available and self._clock() >= self._retry_after
            ):
                result = self._probe()
                self._result = result
                self._retry_after = self._clock() + 30
            return result
        finally:
            self._lock.release()


_probe_cache = _WindowsCudaHealthCache(_probe_windows_cuda_once)


def probe_windows_cuda() -> WindowsCudaHealth:
    """Keep verified success; retry transient failures after thirty seconds."""
    if sys.platform != "win32":
        return WindowsCudaHealth(
            False, "Windows CUDA health is only checked on Windows"
        )
    return _probe_cache.read()
