import importlib
import socket
import sys
from collections.abc import Sequence
from subprocess import CompletedProcess
from typing import NamedTuple
from unittest import mock

import psutil

from exo.utils.info_gatherer import system_info


class _Address(NamedTuple):
    family: socket.AddressFamily
    address: str


_ADAPTERS = {
    "Ethernet 2": [_Address(socket.AF_INET, "192.168.1.20")],
    "Wi-Fi": [_Address(socket.AF_INET, "192.168.1.21")],
    "Local Area Connection": [_Address(socket.AF_INET, "192.168.2.5")],
    "Local Area Connection* 10": [_Address(socket.AF_INET6, "fe80::1")],
    "vEthernet (WSL (Hyper-V firewall))": [_Address(socket.AF_INET, "172.20.0.1")],
    "Tailscale": [_Address(socket.AF_INET, "100.64.0.1")],
}


async def _interface_types(platform: str) -> dict[str, str]:
    with (
        mock.patch.object(sys, "platform", platform),
        mock.patch.object(psutil, "net_if_addrs", lambda: _ADAPTERS),
    ):
        interfaces = await system_info.get_network_interfaces()
    return {info.name: info.interface_type for info in interfaces}


async def test_windows_interface_types_come_from_adapter_names():
    assert await _interface_types("win32") == {
        "Ethernet 2": "ethernet",
        "Wi-Fi": "wifi",
        "Local Area Connection": "ethernet",
        "Local Area Connection* 10": "unknown",
        "vEthernet (WSL (Hyper-V firewall))": "unknown",
        "Tailscale": "unknown",
    }


async def test_adapter_names_are_not_guessed_on_linux():
    assert set((await _interface_types("linux")).values()) == {"unknown"}


def _fake_run_process(calls: list[str], returncode: int):
    outputs = {"powershell": b"ROG STRIX Z890-I\r\n", "nvidia-smi": b"RTX 5070\r\n"}

    async def run_process(
        command: Sequence[str], *, check: bool
    ) -> CompletedProcess[bytes]:
        calls.append(command[0])
        return CompletedProcess(list(command), returncode, outputs[command[0]], b"")

    return run_process


async def test_windows_model_and_gpu_name_are_looked_up_once():
    calls: list[str] = []
    importlib.reload(system_info)  # start without cached lookups

    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(system_info, "run_process", _fake_run_process(calls, 0)),
    ):
        first = await system_info.get_model_and_chip()
        second = await system_info.get_model_and_chip()

    assert first == second == ("ROG STRIX Z890-I", "RTX 5070")
    assert calls == ["powershell", "nvidia-smi"]


async def test_failed_windows_lookups_are_retried():
    calls: list[str] = []
    importlib.reload(system_info)

    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(system_info, "run_process", _fake_run_process(calls, 1)),
    ):
        await system_info.get_model_and_chip()
        await system_info.get_model_and_chip()

    assert calls == ["powershell", "nvidia-smi", "powershell", "nvidia-smi"]


def test_windows_os_version():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch("platform.release", return_value="11"),
    ):
        assert system_info.get_os_version() == "Windows 11"
