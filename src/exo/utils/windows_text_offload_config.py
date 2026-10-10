"""Local Windows text offload policy; GPU and host capacity remain separate."""

import os
import sys
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class WindowsTextOffloadPolicy:
    enabled: bool = False
    host_limit_bytes: int = 0
    stage_limit_bytes: int = 0
    host_reserve_bytes: int = 4 * 1024**3
    gpu_reserve_bytes: int = 2560 * 1024**2
    max_prefill_tokens: int = 256
    max_context_tokens: int = 8192

    def validate(self) -> None:
        if not self.enabled:
            raise ValueError("Windows text RAM offload requires explicit opt-in")
        if (
            min(
                self.host_limit_bytes,
                self.stage_limit_bytes,
                self.max_prefill_tokens,
                self.max_context_tokens,
            )
            <= 0
            or min(self.host_reserve_bytes, self.gpu_reserve_bytes) < 0
        ):
            raise ValueError("Offload limits must be positive and reserves nonnegative")


def _available_host_memory() -> int:
    return int(psutil.virtual_memory().available)


def _positive_limit(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def read_windows_text_offload_policy() -> WindowsTextOffloadPolicy:
    if sys.platform != "win32" or os.environ.get(
        "EXO_WINDOWS_TEXT_OFFLOAD", ""
    ).casefold() not in ("1", "true"):
        return WindowsTextOffloadPolicy()
    host_reserve = 4 * 1024**3
    host_available = max(0, _available_host_memory() - host_reserve)
    if not host_available:
        raise MemoryError("Insufficient host RAM after the 4 GiB offload reserve")
    policy = WindowsTextOffloadPolicy(
        enabled=True,
        host_limit_bytes=min(
            host_available,
            _positive_limit(
                "EXO_WINDOWS_TEXT_OFFLOAD_HOST_LIMIT_BYTES", host_available
            ),
        ),
        stage_limit_bytes=_positive_limit(
            "EXO_WINDOWS_TEXT_OFFLOAD_STAGE_LIMIT_BYTES", 1024**3
        ),
        max_prefill_tokens=_positive_limit(
            "EXO_WINDOWS_TEXT_OFFLOAD_PREFILL_TOKENS", 256
        ),
        max_context_tokens=_positive_limit(
            "EXO_WINDOWS_TEXT_OFFLOAD_CONTEXT_TOKENS", 8192
        ),
    )
    policy.validate()
    return policy
