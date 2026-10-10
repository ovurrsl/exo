import atexit
import sys
import types
from collections.abc import Callable
from unittest import mock

import pytest

from exo.utils.win32_mlx_exit import install_windows_mlx_exit_hook


def _registered_exit_hooks(platform: str) -> list[Callable[[], None]]:
    hooks: list[Callable[[], None]] = []
    with (
        mock.patch.object(sys, "platform", platform),
        mock.patch.object(atexit, "register", hooks.append),
    ):
        install_windows_mlx_exit_hook()
    return hooks


def _fake_mlx(clear_streams: Callable[[], None]) -> dict[str, types.ModuleType]:
    core = types.ModuleType("mlx.core")
    core.__dict__["clear_streams"] = clear_streams
    mlx = types.ModuleType("mlx")
    mlx.__dict__["core"] = core
    return {"mlx": mlx, "mlx.core": core}


def test_exit_hook_is_only_registered_on_windows():
    assert _registered_exit_hooks("darwin") == []
    assert _registered_exit_hooks("linux") == []
    assert len(_registered_exit_hooks("win32")) == 1


def test_exit_hook_releases_mlx_streams():
    calls: list[str] = []
    (hook,) = _registered_exit_hooks("win32")

    with mock.patch.dict(sys.modules, _fake_mlx(lambda: calls.append("clear"))):
        hook()

    assert calls == ["clear"]


def test_exit_hook_does_not_import_mlx():
    (hook,) = _registered_exit_hooks("win32")

    with mock.patch.dict(sys.modules):
        for name in [n for n in sys.modules if n == "mlx" or n.startswith("mlx.")]:
            del sys.modules[name]
        hook()
        assert "mlx.core" not in sys.modules


def test_exit_hook_never_raises(capsys: pytest.CaptureFixture[str]):
    def clear_streams() -> None:
        raise RuntimeError("driver shutting down")

    (hook,) = _registered_exit_hooks("win32")

    with mock.patch.dict(sys.modules, _fake_mlx(clear_streams)):
        hook()

    assert "mx.clear_streams() at exit failed" in capsys.readouterr().err
