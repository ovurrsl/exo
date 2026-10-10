import ctypes
import platform
import re
import socket
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from subprocess import CalledProcessError
from typing import cast, final

import psutil
from anyio import fail_after, run_process

from exo.shared.types.profiling import InterfaceType, NetworkInterfaceInfo


def get_os_version() -> str:
    """Return the OS version string for this node.

    On macOS this is the macOS version (e.g. ``"15.3"``).
    On Windows this is ``"Windows 10"`` / ``"Windows 11"``.
    On other platforms it falls back to the platform name (e.g. ``"Linux"``).
    """
    if sys.platform == "darwin":
        version = platform.mac_ver()[0]
        return version if version else "Unknown"
    if sys.platform == "win32":
        release = platform.release()
        return f"Windows {release}" if release else "Windows"
    return platform.system() or "Unknown"


async def get_os_build_version() -> str:
    """Return the OS build version string (e.g. ``"24D5055b"`` on macOS).

    On Windows this is the kernel version (e.g. ``"10.0.19045"``).
    On other non-macOS platforms, returns ``"Unknown"``.
    """
    if sys.platform == "win32":
        return platform.version() or "Unknown"

    if sys.platform != "darwin":
        return "Unknown"

    try:
        process = await run_process(["sw_vers", "-buildVersion"])
    except CalledProcessError:
        return "Unknown"

    return process.stdout.decode("utf-8", errors="replace").strip() or "Unknown"


async def get_friendly_name() -> str:
    """
    Asynchronously gets the 'Computer Name' (friendly name) of a Mac.
    e.g., "John's MacBook Pro"
    Returns the name as a string, or None if an error occurs or not on macOS.
    """
    hostname = socket.gethostname()

    if sys.platform != "darwin":
        return hostname

    try:
        process = await run_process(["scutil", "--get", "ComputerName"])
    except CalledProcessError:
        return hostname

    return process.stdout.decode("utf-8", errors="replace").strip() or hostname


async def _get_interface_types_from_networksetup() -> dict[str, InterfaceType]:
    """Parse networksetup -listallhardwareports to get interface types."""
    if sys.platform != "darwin":
        return {}

    try:
        result = await run_process(["networksetup", "-listallhardwareports"])
    except CalledProcessError:
        return {}

    types: dict[str, InterfaceType] = {}
    current_type: InterfaceType = "unknown"

    for line in result.stdout.decode().splitlines():
        if line.startswith("Hardware Port:"):
            port_name = line.split(":", 1)[1].strip()
            if "Wi-Fi" in port_name:
                current_type = "wifi"
            elif "Ethernet" in port_name or "LAN" in port_name:
                current_type = "ethernet"
            elif port_name.startswith("Thunderbolt"):
                current_type = "thunderbolt"
            else:
                current_type = "unknown"
        elif line.startswith("Device:"):
            device = line.split(":", 1)[1].strip()
            # enX is ethernet adapters or thunderbolt - these must be deprioritised
            if device.startswith("en") and device not in ["en0", "en1"]:
                current_type = "maybe_ethernet"
            types[device] = current_type

    return types


async def get_network_interfaces() -> list[NetworkInterfaceInfo]:
    """
    Retrieves detailed network interface information on macOS.
    Parses output from 'networksetup -listallhardwareports' and 'ifconfig'
    to determine interface names, IP addresses, and types (ethernet, wifi, vpn, other).
    Returns a list of NetworkInterfaceInfo objects.
    """
    interfaces_info: list[NetworkInterfaceInfo] = []
    interface_types = await _get_interface_types_from_networksetup()
    adapter_descriptions = _windows_adapter_descriptions()

    for iface, services in psutil.net_if_addrs().items():
        iface_type = interface_types.get(
            iface,
            _guess_windows_interface_type(iface, adapter_descriptions.get(iface, "")),
        )
        for service in services:
            match service.family:
                case socket.AF_INET | socket.AF_INET6:
                    interfaces_info.append(
                        NetworkInterfaceInfo(
                            name=iface,
                            ip_address=service.address,
                            interface_type=iface_type,
                        )
                    )
                case _:
                    pass

    return interfaces_info


_WINDOWS_VIRTUAL_ADAPTER_MARKERS = (
    "vethernet",
    "hyper-v",
    "virtualbox",
    "vmware",
    "loopback",
    "bluetooth",
    "tailscale",
    "zerotier",
    "wireguard",
    "openvpn",
    "tap-",
)

# Wi-Fi Direct virtual adapters are named "<localized name>* <n>", e.g.
# "Local Area Connection* 10" or "Yerel Ağ Bağlantısı* 3"; a wired adapter's
# legacy name has no asterisk.
_WINDOWS_WIFI_DIRECT_NAME = re.compile(r"\*\s*\d+$")


# A cable between two computers' USB4 or Thunderbolt ports is a network
# adapter whose friendly name is just "Ethernet <n>"; only its driver
# description tells it apart: "USB4(TM) P2P Network Adapter" (Windows 11's
# USB4 networking, which Macs' Thunderbolt Bridge connects to) or
# "Thunderbolt(TM) Networking" (Intel's older Thunderbolt 3 driver). An
# Ethernet adapter inside a Thunderbolt dock is not matched.
_WINDOWS_HOST_TO_HOST_LINK = re.compile(r"usb4|thunderbolt\S*\s+network", re.IGNORECASE)

_WINDOWS_NETWORK_CLASS_KEY = (
    r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
)
_WINDOWS_NETWORK_CONNECTIONS_KEY = (
    r"SYSTEM\CurrentControlSet\Control\Network\{4d36e972-e325-11ce-bfc1-08002be10318}"
)

# Win32 CREATE_NO_WINDOW. Kept numeric so mocked Windows tests work on POSIX.
_WINDOWS_NO_CONSOLE = 0x08000000
_WINDOWS_QUERY_TIMEOUT = 5


def _windows_system_directory() -> Path:
    # kernel32 is a Windows KnownDLL; do not trust a process environment path.
    win_dll = cast(type[ctypes.CDLL], getattr(ctypes, "WinDLL"))  # noqa: B009
    kernel = win_dll("kernel32", use_last_error=True)
    kernel.GetSystemDirectoryW.argtypes = [
        ctypes.POINTER(ctypes.c_wchar),
        ctypes.c_uint,
    ]
    kernel.GetSystemDirectoryW.restype = ctypes.c_uint
    get_directory = cast(
        Callable[[ctypes.Array[ctypes.c_wchar], int], int], kernel.GetSystemDirectoryW
    )
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_directory(buffer, len(buffer))
    if length <= 0 or length >= len(buffer):
        raise OSError("Windows system directory could not be resolved")
    return Path(cast(str, cast(object, buffer.value)))


def _windows_program_files_directory(system_directory: Path) -> Path:
    win_dll = cast(type[ctypes.CDLL], getattr(ctypes, "WinDLL"))  # noqa: B009
    shell = win_dll(str(system_directory / "shell32.dll"), use_last_error=True)
    shell.SHGetFolderPathW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_wchar),
    ]
    shell.SHGetFolderPathW.restype = ctypes.c_long
    get_directory = cast(
        Callable[[None, int, None, int, ctypes.Array[ctypes.c_wchar]], int],
        shell.SHGetFolderPathW,
    )
    buffer = ctypes.create_unicode_buffer(32768)
    # CSIDL_PROGRAM_FILES uses Windows' protected known-folder configuration.
    result = get_directory(None, 0x26, None, 0, buffer)
    value = cast(str, cast(object, buffer.value))
    if result != 0 or not value:
        raise OSError("Windows Program Files directory could not be resolved")
    return Path(value)


def _windows_gpu_executable(system_directory: Path) -> Path | None:
    driver_executable = system_directory / "nvidia-smi.exe"
    if driver_executable.is_file():
        return driver_executable
    legacy_executable = (
        _windows_program_files_directory(system_directory)
        / "NVIDIA Corporation"
        / "NVSMI"
        / "nvidia-smi.exe"
    )
    return legacy_executable if legacy_executable.is_file() else None


def _windows_adapter_descriptions() -> dict[str, str]:
    """Windows network adapters' friendly names (as psutil reports them),
    mapped to their driver descriptions, read from the registry.

    Empty on other platforms or if the registry cannot be read; adapters
    whose keys cannot be read are left out.
    """
    if sys.platform != "win32":
        return {}
    import winreg

    try:
        adapters = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _WINDOWS_NETWORK_CLASS_KEY)
    except OSError:
        return {}  # adapter names alone still classify most adapters
    descriptions_by_id: dict[str, str] = {}
    with adapters:
        index = 0
        while True:
            try:
                subkey = winreg.EnumKey(adapters, index)
            except OSError:
                break  # no more subkeys
            index += 1
            try:
                with winreg.OpenKey(adapters, subkey) as adapter:
                    instance_id = str(
                        cast(
                            object, winreg.QueryValueEx(adapter, "NetCfgInstanceId")[0]
                        )
                    )
                    description = str(
                        cast(object, winreg.QueryValueEx(adapter, "DriverDesc")[0])
                    )
            except OSError:
                continue  # e.g. the "Properties" subkey, or no access
            descriptions_by_id[instance_id] = description

    descriptions: dict[str, str] = {}
    for instance_id, description in descriptions_by_id.items():
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                rf"{_WINDOWS_NETWORK_CONNECTIONS_KEY}\{instance_id}\Connection",
            ) as connection:
                name = str(cast(object, winreg.QueryValueEx(connection, "Name")[0]))
        except OSError:
            continue  # an adapter without a network connection
        descriptions[name] = description
    return descriptions


def _guess_windows_interface_type(iface: str, description: str) -> InterfaceType:
    """Best-effort interface type from a Windows adapter's friendly name and
    driver description.

    Windows has no networksetup equivalent, so names such as "Ethernet 2" and
    "Wi-Fi" are the only cheap signal, except for a USB4/Thunderbolt cable to
    another computer, which only its description identifies; that is reported
    as "thunderbolt", the link the ring backend prefers. Virtual adapters
    (Hyper-V/WSL switches, VPN tunnels, VM host-only networks) are reported as
    "unknown" so placement never prefers them over physical links. Other
    platforms keep upstream behaviour and report "unknown" for anything
    networksetup did not classify.
    """
    if sys.platform != "win32":
        return "unknown"
    if _WINDOWS_HOST_TO_HOST_LINK.search(description):
        return "thunderbolt"
    lowered = iface.lower()
    if _WINDOWS_WIFI_DIRECT_NAME.search(iface) or any(
        marker in lowered for marker in _WINDOWS_VIRTUAL_ADAPTER_MARKERS
    ):
        return "unknown"
    if "wi-fi" in lowered or "wireless" in lowered or "wlan" in lowered:
        return "wifi"
    if lowered.startswith("ethernet") or "local area connection" in lowered:
        return "ethernet"
    return "unknown"


async def get_model_and_chip() -> tuple[str, str]:
    """Get machine model and accelerator/chip names."""
    model = "Unknown Model"
    chip = "Unknown Chip"

    if sys.platform == "win32":
        uname = platform.uname()
        model = (await _windows_computer_model()) or (
            f"{uname.system} {uname.release}".strip() or "Windows PC"
        )
        chip = (
            (await _windows_gpu_name())
            or uname.processor
            or uname.machine
            or "Unknown Chip"
        )
        return (model, chip)

    if sys.platform != "darwin":
        return (model, chip)

    try:
        process = await run_process(
            [
                "system_profiler",
                "SPHardwareDataType",
            ]
        )
    except CalledProcessError:
        return (model, chip)

    # less interested in errors here because this value should be hard coded
    output = process.stdout.decode().strip()

    model_line = next(
        (line for line in output.split("\n") if "Model Name" in line), None
    )
    model = model_line.split(": ")[1] if model_line else "Unknown Model"

    chip_line = next((line for line in output.split("\n") if "Chip" in line), None)
    chip = chip_line.split(": ")[1] if chip_line else "Unknown Chip"

    return (model, chip)


async def _query_windows_computer_model() -> str | None:
    try:
        with fail_after(_WINDOWS_QUERY_TIMEOUT):
            process = await run_process(
                [
                    str(
                        _windows_system_directory()
                        / "WindowsPowerShell"
                        / "v1.0"
                        / "powershell.exe"
                    ),
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "(Get-CimInstance -ClassName Win32_ComputerSystem).Model",
                ],
                check=False,
                creationflags=_WINDOWS_NO_CONSOLE if sys.platform == "win32" else 0,
            )
    except (OSError, TimeoutError):
        return None
    if process.returncode != 0:
        return None
    model = process.stdout.decode("utf-8", errors="replace").strip()
    return model or None


async def _query_windows_gpu_name() -> str | None:
    try:
        executable = _windows_gpu_executable(_windows_system_directory())
        if executable is None:
            return None
        with fail_after(_WINDOWS_QUERY_TIMEOUT):
            process = await run_process(
                [
                    str(executable),
                    "--query-gpu=name",
                    "--format=csv,noheader",
                ],
                check=False,
                creationflags=_WINDOWS_NO_CONSOLE if sys.platform == "win32" else 0,
            )
    except (OSError, TimeoutError):
        return None
    if process.returncode != 0:
        return None
    names = [
        line.strip()
        for line in process.stdout.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    return ", ".join(names) if names else None


@final
class _CachedLookup:
    """Remember the first successful result of a lookup; retry failed ones.

    Static node info is gathered again every minute, but the computer model and
    GPU name cannot change while exo runs, so there is no need to start
    powershell and nvidia-smi each time.
    """

    def __init__(self, lookup: Callable[[], Awaitable[str | None]]) -> None:
        self._lookup = lookup
        self._value: str | None = None

    async def __call__(self) -> str | None:
        if self._value is None:
            self._value = await self._lookup()
        return self._value


_windows_computer_model = _CachedLookup(_query_windows_computer_model)
_windows_gpu_name = _CachedLookup(_query_windows_gpu_name)
