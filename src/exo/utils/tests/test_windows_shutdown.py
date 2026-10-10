import ctypes
import sys
import uuid
from collections.abc import Callable
from typing import cast

import anyio
import pytest

from exo import __version__
from exo.main import Args
from exo.utils.windows_shutdown import (
    WindowsShutdownEvent,
    watch_windows_shutdown_event,
)


@pytest.mark.parametrize("namespace", [None, "", "   "])
def test_namespace_defaults_to_version(
    monkeypatch: pytest.MonkeyPatch, namespace: str | None
) -> None:
    monkeypatch.setattr(sys, "argv", ["exo"])
    monkeypatch.delenv("EXO_ZENOH_NAMESPACE", raising=False)
    if namespace is not None:
        monkeypatch.setenv("EXO_ZENOH_NAMESPACE", namespace)
    assert Args.parse().namespace == __version__


def test_namespace_environment_and_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXO_ZENOH_NAMESPACE", "  mac-app-release  ")
    monkeypatch.setattr(sys, "argv", ["exo"])
    assert Args.parse().namespace == "mac-app-release"
    monkeypatch.setattr(sys, "argv", ["exo", "--namespace", "cluster-test"])
    assert Args.parse().namespace == "cluster-test"


@pytest.mark.parametrize("name", ["Global\\shutdown", "Local\\exo-shutdown-abc", ""])
def test_shutdown_event_rejects_unowned_names(name: str) -> None:
    with pytest.raises(ValueError, match="Invalid"):
        WindowsShutdownEvent(name)


async def test_cli_does_not_watch_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXO_WINDOWS_SHUTDOWN_EVENT", raising=False)
    calls: list[bool] = []
    await watch_windows_shutdown_event(lambda: calls.append(True))
    assert not calls


@pytest.mark.skipif(sys.platform != "win32", reason="Windows named event integration")
async def test_real_named_event_shutdown_and_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows named event integration")
    win_dll = cast(type[ctypes.CDLL], ctypes.WinDLL)
    kernel = win_dll("kernel32", use_last_error=True)
    kernel.CreateEventW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_wchar_p,
    ]
    kernel.CreateEventW.restype = ctypes.c_void_p
    kernel.SetEvent.argtypes = [ctypes.c_void_p]
    kernel.SetEvent.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    create = cast(Callable[[None, int, int, str], int | None], kernel.CreateEventW)
    signal = cast(Callable[[int], int], kernel.SetEvent)
    close = cast(Callable[[int], int], kernel.CloseHandle)
    name = f"Local\\exo-shutdown-{uuid.uuid4().hex}"
    handle = create(None, 1, 0, name)
    assert handle is not None
    monkeypatch.setenv("EXO_WINDOWS_SHUTDOWN_EVENT", name)
    stopped = anyio.Event()
    try:
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(watch_windows_shutdown_event, stopped.set)
            await anyio.sleep(0.05)
            assert signal(handle)
            with anyio.fail_after(2):
                await stopped.wait()
        # An unsignalled event can also be cancelled without a leaked wait thread.
        kernel.ResetEvent.argtypes = [ctypes.c_void_p]
        reset = cast(Callable[[int], int], kernel.ResetEvent)
        assert reset(handle)
        with anyio.move_on_after(0.05) as scope:
            await watch_windows_shutdown_event(stopped.set)
        assert scope.cancel_called
    finally:
        assert close(handle)
