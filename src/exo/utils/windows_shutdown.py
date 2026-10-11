"""Private shutdown IPC for the Windows desktop application's owned node."""

import ctypes
import os
import re
import sys
from collections.abc import Callable
from typing import Self, cast

from anyio import to_thread

_EVENT_ENVIRONMENT = "EXO_WINDOWS_SHUTDOWN_EVENT"
_EVENT_NAME = re.compile(r"Local\\exo-shutdown-[0-9a-f]{32}\Z")
_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258


class WindowsShutdownEvent:
    def __init__(self, name: str) -> None:
        if not _EVENT_NAME.fullmatch(name):
            raise ValueError("Invalid EXO_WINDOWS_SHUTDOWN_EVENT name")
        # Resolve the Windows-only ctypes API without importing it on macOS.
        win_dll = cast(type[ctypes.CDLL], getattr(ctypes, "WinDLL"))  # noqa: B009
        kernel = win_dll("kernel32", use_last_error=True)
        kernel.OpenEventW.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_wchar_p]
        kernel.OpenEventW.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.WaitForSingleObject.restype = ctypes.c_ulong
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.restype = ctypes.c_int
        open_event = cast(Callable[[int, int, str], int | None], kernel.OpenEventW)
        self._wait = cast(Callable[[int, int], int], kernel.WaitForSingleObject)
        self._close = cast(Callable[[int], int], kernel.CloseHandle)
        handle = open_event(_SYNCHRONIZE, 0, name)
        if handle is None:
            raise cast(Callable[[], OSError], getattr(ctypes, "WinError"))()  # noqa: B009
        self._handle = handle

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exception: object) -> None:
        self._close(self._handle)

    def wait(self) -> bool:
        # Bounded waits let cancellation close the handle without leaving a thread.
        result = self._wait(self._handle, 250)
        if result == _WAIT_OBJECT_0:
            return True
        if result == _WAIT_TIMEOUT:
            return False
        raise cast(Callable[[], OSError], getattr(ctypes, "WinError"))()  # noqa: B009


async def watch_windows_shutdown_event(shutdown: Callable[[], None]) -> None:
    """Watch only the session-local event explicitly supplied by the desktop app.

    CLI and non-Windows nodes do not create or open IPC objects. The app creates
    the randomly named event with the current user's ACL before spawning EXO.
    """
    if sys.platform != "win32":
        return
    name = os.environ.get(_EVENT_ENVIRONMENT)
    if not name:
        return
    with WindowsShutdownEvent(name) as event:
        while not await to_thread.run_sync(event.wait):
            pass
        shutdown()
