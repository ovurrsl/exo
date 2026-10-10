from types import TracebackType
from typing import TextIO

class DaemonContext:
    def __init__(
        self,
        *,
        detach_process: bool,
        files_preserve: list[int],
        stdin: TextIO,
        stdout: TextIO,
        stderr: TextIO,
    ) -> None: ...
    def __enter__(self) -> DaemonContext: ...
    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...
