import importlib
import socket
import sys
import types
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from subprocess import CompletedProcess
from typing import NamedTuple, Self
from unittest import mock

import psutil
import pytest
from anyio import sleep_forever

from exo.utils.info_gatherer import system_info


class _Address(NamedTuple):
    family: socket.AddressFamily
    address: str


_ADAPTERS = {
    "Ethernet 2": [_Address(socket.AF_INET, "192.168.1.20")],
    "Wi-Fi": [_Address(socket.AF_INET, "192.168.1.21")],
    "Local Area Connection": [_Address(socket.AF_INET, "192.168.2.5")],
    "Local Area Connection* 10": [_Address(socket.AF_INET6, "fe80::1")],
    "Yerel Ağ Bağlantısı* 3": [_Address(socket.AF_INET6, "fe80::2")],
    "vEthernet (WSL (Hyper-V firewall))": [_Address(socket.AF_INET, "172.20.0.1")],
    "Tailscale": [_Address(socket.AF_INET, "100.64.0.1")],
    "Ethernet 3": [_Address(socket.AF_INET, "169.254.10.2")],
    "Ethernet 4": [_Address(socket.AF_INET, "192.168.1.30")],
}

_CLASS_KEY = (
    r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
)
_CONNECTIONS_KEY = (
    r"SYSTEM\CurrentControlSet\Control\Network\{4d36e972-e325-11ce-bfc1-08002be10318}"
)


def _adapter(index: str, instance_id: str, description: str, name: str):
    return {
        rf"{_CLASS_KEY}\{index}": {
            "NetCfgInstanceId": instance_id,
            "DriverDesc": description,
        },
        rf"{_CONNECTIONS_KEY}\{instance_id}\Connection": {"Name": name},
    }


# Registry keys (path -> values) of the adapters above that have a driver.
_REGISTRY = {
    **_adapter("0000", "{A}", "Intel(R) Ethernet Controller I226-V", "Ethernet 2"),
    **_adapter("0001", "{B}", "Intel(R) Wi-Fi 7 BE200 320MHz", "Wi-Fi"),
    **_adapter("0002", "{C}", "USB4(TM) P2P Network Adapter", "Ethernet 3"),
    **_adapter("0003", "{D}", "Thunderbolt(TM) 3 Dock Ethernet", "Ethernet 4"),
    rf"{_CLASS_KEY}\Properties": {},
}


class _FakeKey:
    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exception: object) -> None:
        pass


def _fake_winreg(registry: dict[str, dict[str, str]]) -> types.ModuleType:
    """A winreg module backed by `registry`; key paths are case-insensitive."""
    keys = {path.lower(): values for path, values in registry.items()}
    root = _FakeKey("")

    def open_key(parent: _FakeKey, subkey: str) -> _FakeKey:
        path = subkey if parent is root else rf"{parent.path}\{subkey}"
        if not any(
            k == path.lower() or k.startswith(path.lower() + "\\") for k in keys
        ):
            raise OSError(f"no key {path}")
        return _FakeKey(path)

    def enum_key(key: _FakeKey, index: int) -> str:
        prefix = key.path.lower() + "\\"
        children = sorted(
            {k[len(prefix) :].split("\\")[0] for k in keys if k.startswith(prefix)}
        )
        if index >= len(children):
            raise OSError("no more subkeys")
        return children[index]

    def query_value_ex(key: _FakeKey, name: str) -> tuple[str, int]:
        values = keys.get(key.path.lower(), {})
        if name not in values:
            raise OSError(f"no value {name}")
        return values[name], 1

    winreg = types.ModuleType("winreg")
    winreg.__dict__.update(
        HKEY_LOCAL_MACHINE=root,
        OpenKey=open_key,
        EnumKey=enum_key,
        QueryValueEx=query_value_ex,
    )
    return winreg


async def _interface_types(
    platform: str, registry: dict[str, dict[str, str]] = _REGISTRY
) -> dict[str, str]:
    with (
        mock.patch.object(sys, "platform", platform),
        mock.patch.object(psutil, "net_if_addrs", lambda: _ADAPTERS),
        mock.patch.dict(sys.modules, {"winreg": _fake_winreg(registry)}),
    ):
        interfaces = await system_info.get_network_interfaces()
    return {info.name: info.interface_type for info in interfaces}


async def test_windows_interface_types_come_from_adapter_names():
    assert await _interface_types("win32") == {
        "Ethernet 2": "ethernet",
        "Wi-Fi": "wifi",
        "Local Area Connection": "ethernet",
        "Local Area Connection* 10": "unknown",
        "Yerel Ağ Bağlantısı* 3": "unknown",
        "vEthernet (WSL (Hyper-V firewall))": "unknown",
        "Tailscale": "unknown",
        "Ethernet 3": "thunderbolt",
        "Ethernet 4": "ethernet",
    }


async def test_unreadable_registry_falls_back_to_adapter_names():
    types_by_name = await _interface_types("win32", registry={})

    assert types_by_name["Ethernet 3"] == "ethernet"
    assert types_by_name["Wi-Fi"] == "wifi"


def test_windows_adapter_descriptions_come_from_the_registry():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.dict(sys.modules, {"winreg": _fake_winreg(_REGISTRY)}),
    ):
        descriptions = system_info._windows_adapter_descriptions()  # pyright: ignore[reportPrivateUsage]

    assert descriptions == {
        "Ethernet 2": "Intel(R) Ethernet Controller I226-V",
        "Wi-Fi": "Intel(R) Wi-Fi 7 BE200 320MHz",
        "Ethernet 3": "USB4(TM) P2P Network Adapter",
        "Ethernet 4": "Thunderbolt(TM) 3 Dock Ethernet",
    }


def test_thunderbolt_networking_driver_is_a_host_to_host_link():
    with mock.patch.object(sys, "platform", "win32"):
        guess = system_info._guess_windows_interface_type  # pyright: ignore[reportPrivateUsage]

        assert guess("Ethernet 5", "Thunderbolt(TM) Networking") == "thunderbolt"
        assert guess("Ethernet 5", "Realtek USB GbE Family Controller") == "ethernet"


async def test_adapter_names_are_not_guessed_on_linux():
    assert set((await _interface_types("linux")).values()) == {"unknown"}


def _fake_run_process(calls: list[str], returncode: int):
    outputs = {
        "powershell.exe": b"ROG STRIX Z890-I\r\n",
        "nvidia-smi.exe": b"RTX 5070\r\n",
    }

    async def run_process(
        command: Sequence[str], *, check: bool, creationflags: int
    ) -> CompletedProcess[bytes]:
        assert not check
        assert creationflags == 0x08000000
        name = Path(command[0]).name.lower()
        if name == "powershell.exe":
            assert "-NonInteractive" in command
        calls.append(name)
        return CompletedProcess(list(command), returncode, outputs[name], b"")

    return run_process


async def test_windows_model_and_gpu_name_are_looked_up_once():
    calls: list[str] = []
    importlib.reload(system_info)  # start without cached lookups

    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(system_info, "run_process", _fake_run_process(calls, 0)),
        mock.patch.object(
            system_info,
            "_windows_system_directory",
            return_value=Path.cwd() / "trusted-system",
        ),
        mock.patch.object(
            system_info,
            "_windows_gpu_executable",
            return_value=Path.cwd() / "trusted-system" / "nvidia-smi.exe",
        ),
    ):
        first = await system_info.get_model_and_chip()
        second = await system_info.get_model_and_chip()

    assert first == second == ("ROG STRIX Z890-I", "RTX 5070")
    assert calls == ["powershell.exe", "nvidia-smi.exe"]


async def test_failed_windows_lookups_are_retried():
    calls: list[str] = []
    importlib.reload(system_info)

    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(system_info, "run_process", _fake_run_process(calls, 1)),
        mock.patch.object(
            system_info,
            "_windows_system_directory",
            return_value=Path.cwd() / "trusted-system",
        ),
        mock.patch.object(
            system_info,
            "_windows_gpu_executable",
            return_value=Path.cwd() / "trusted-system" / "nvidia-smi.exe",
        ),
    ):
        await system_info.get_model_and_chip()
        await system_info.get_model_and_chip()

    assert calls == [
        "powershell.exe",
        "nvidia-smi.exe",
        "powershell.exe",
        "nvidia-smi.exe",
    ]


@pytest.mark.parametrize(
    "lookup",
    [
        system_info._query_windows_computer_model,  # pyright: ignore[reportPrivateUsage]
        system_info._query_windows_gpu_name,  # pyright: ignore[reportPrivateUsage]
    ],
)
async def test_stalled_windows_lookup_returns_unknown_after_deadline(
    lookup: Callable[[], Awaitable[str | None]],
) -> None:
    async def blocked_process(
        _command: Sequence[str], *, check: bool, creationflags: int
    ) -> CompletedProcess[bytes]:
        assert not check
        assert creationflags == 0x08000000
        await sleep_forever()
        raise AssertionError("A blocked subprocess unexpectedly completed")

    with (
        mock.patch.object(system_info, "sys", types.SimpleNamespace(platform="win32")),
        mock.patch.object(system_info, "run_process", blocked_process),
        mock.patch.object(system_info, "_WINDOWS_QUERY_TIMEOUT", 0.01),
        mock.patch.object(
            system_info,
            "_windows_system_directory",
            return_value=Path.cwd() / "trusted-system",
        ),
        mock.patch.object(
            system_info,
            "_windows_gpu_executable",
            return_value=Path.cwd() / "trusted-system" / "nvidia-smi.exe",
        ),
    ):
        assert await lookup() is None


async def test_windows_queries_do_not_resolve_executables_from_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trusted_system = tmp_path / "protected-system"
    trusted_system.mkdir()
    (trusted_system / "nvidia-smi.exe").write_bytes(b"trusted driver helper")
    working_directory = tmp_path / "untrusted-working-directory"
    working_directory.mkdir()
    for name in ("powershell.exe", "nvidia-smi.exe"):
        (working_directory / name).write_bytes(b"untrusted executable")
    monkeypatch.chdir(working_directory)
    monkeypatch.setattr(system_info, "sys", types.SimpleNamespace(platform="win32"))
    monkeypatch.setattr(
        system_info, "_windows_system_directory", lambda: trusted_system
    )
    commands: list[str] = []

    async def run_process(
        command: Sequence[str], *, check: bool, creationflags: int
    ) -> CompletedProcess[bytes]:
        commands.append(command[0])
        return CompletedProcess(list(command), 0, b"test hardware\n", b"")

    monkeypatch.setattr(system_info, "run_process", run_process)
    await system_info._query_windows_computer_model()  # pyright: ignore[reportPrivateUsage]
    await system_info._query_windows_gpu_name()  # pyright: ignore[reportPrivateUsage]
    assert commands == [
        str(trusted_system / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
        str(trusted_system / "nvidia-smi.exe"),
    ]


def test_legacy_nvidia_helper_uses_the_protected_program_files_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    system = tmp_path / "protected-system"
    system.mkdir()
    program_files = tmp_path / "protected-program-files"
    legacy = program_files / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy protected NVIDIA executable")

    def known_folder(_system: Path) -> Path:
        return program_files

    monkeypatch.setattr(system_info, "_windows_program_files_directory", known_folder)
    find_executable = system_info._windows_gpu_executable  # pyright: ignore[reportPrivateUsage]
    assert find_executable(system) == legacy
    current = system / "nvidia-smi.exe"
    current.write_bytes(b"current protected NVIDIA executable")
    assert find_executable(system) == current


def test_windows_os_version():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch("platform.release", return_value="11"),
    ):
        assert system_info.get_os_version() == "Windows 11"
