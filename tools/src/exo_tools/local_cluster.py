"""Run a multi-node exo cluster as local processes on a single host.

`EcoSession` deploys exo across real machines through the `eco` CLI, which is
not available outside the lab. `LocalProcessSession` offers the same surface
backed by several `exo` processes on one machine, each on its own API, zenoh
and discovery port and all sharing one discovery namespace. That is enough to
exercise discovery, election, placement and the API, and it makes
`disconnect_node` / `reconnect_node` mean "stop and restart a process" rather
than "power-cycle a Mac".

It is deliberately a sibling of `EcoSession` rather than a replacement: the two
answer different questions, and only a real deployment can tell you anything
about Thunderbolt, RDMA or Metal.

Requires IPv6. exo's peer discovery joins an IPv6 multicast group
(`rust/networking/src/discovery.rs`) and zenoh listens on `tcp/[::]`, so on a
host built without IPv6 support a node cannot start at all - loopback-only IPv6
is enough, a routable address is not needed.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import signal
import socket
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .cluster import ClusterInfo

__all__ = [
    "LocalNode",
    "LocalProcessSession",
    "PortAllocation",
    "allocate_ports",
    "build_node_command",
    "ipv6_is_available",
]

# exo's own defaults, so a single-node local session looks like a plain
# `uv run exo` to anything reading the API.
DEFAULT_API_PORT = 52415
DEFAULT_ZENOH_PORT = 52414
DEFAULT_DISCOVERY_PORT = 52413

# Each node claims a contiguous block, so node N never collides with node N+1
# no matter which of the three ports moves first.
PORT_STRIDE = 10

STOP_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class PortAllocation:
    """The three ports one local node listens on."""

    api: int
    zenoh: int
    discovery: int


def allocate_ports(index: int) -> PortAllocation:
    """Ports for the node at `index`, counting from zero.

    Pure so a test can assert the layout without binding anything.
    """
    if index < 0:
        raise ValueError(f"Node index must not be negative: {index}")
    offset = index * PORT_STRIDE
    return PortAllocation(
        api=DEFAULT_API_PORT + offset,
        zenoh=DEFAULT_ZENOH_PORT + offset,
        discovery=DEFAULT_DISCOVERY_PORT + offset,
    )


def ipv6_is_available() -> bool:
    """Whether this host can open an IPv6 socket at all.

    Checked up front because the failure otherwise surfaces deep inside zenoh
    as `Address family not supported by protocol`, which does not point at the
    cause.
    """
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.bind(("::", 0))
    except OSError:
        return False
    return True


def build_node_command(
    ports: PortAllocation,
    namespace: str,
    *,
    executable: Sequence[str] = ("uv", "run", "exo"),
    offline: bool = False,
    extra_arguments: Sequence[str] = (),
) -> list[str]:
    """The argv for one node. Pure, so the flags are testable without spawning."""
    command = [
        *executable,
        "--api-port",
        str(ports.api),
        "--zenoh-port",
        str(ports.zenoh),
        "--discovery-port",
        str(ports.discovery),
        "--namespace",
        namespace,
    ]
    if offline:
        command.append("--offline")
    command.extend(extra_arguments)
    return command


@dataclass
class LocalNode:
    """One exo process, and everything needed to restart it unchanged."""

    name: str
    ports: PortAllocation
    log_path: Path
    command: list[str]
    process: subprocess.Popen[bytes] | None = field(default=None, repr=False)

    @property
    def api_url(self) -> str:
        return f"http://127.0.0.1:{self.ports.api}"

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


# Injected so tests can drive the lifecycle without starting real processes.
Launcher = Callable[[Sequence[str], Path, Mapping[str, str]], "subprocess.Popen[bytes]"]


def _spawn(
    command: Sequence[str], log_path: Path, environment: Mapping[str, str]
) -> subprocess.Popen[bytes]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("ab")
    return subprocess.Popen(
        list(command),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=dict(environment),
        start_new_session=True,
    )


class LocalProcessSession:
    """`EcoSession`'s surface, backed by local processes.

    Host names are synthetic (`local-0`, `local-1`, ...) and are what the
    `ClusterInfo` returned by `start_deploy` is keyed on, so the existing test
    framework's `disconnect_node(index)` addresses them unchanged.

    Usage:
        session = LocalProcessSession(log_dir=Path("/tmp/exo-local"))
        cluster = session.start_deploy(count=2)
        ...
        session.stop_all()   # also runs at interpreter exit
    """

    def __init__(
        self,
        *,
        log_dir: Path,
        namespace: str | None = None,
        offline: bool = False,
        executable: Sequence[str] = ("uv", "run", "exo"),
        environment: Mapping[str, str] | None = None,
        launcher: Launcher = _spawn,
    ) -> None:
        self._session_id = uuid.uuid4().hex[:8]
        self.namespace = namespace or f"local-{self._session_id}"
        self._log_dir = log_dir
        self._offline = offline
        self._executable = tuple(executable)
        self._environment = dict(environment if environment is not None else os.environ)
        self._launcher = launcher
        self._nodes: dict[str, LocalNode] = {}

        atexit.register(self.stop_all)
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with contextlib.suppress(ValueError):
                _ = signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum: int, _frame: object) -> None:
        self.stop_all()
        raise SystemExit(128 + signum)

    @property
    def nodes(self) -> Mapping[str, LocalNode]:
        return self._nodes

    def start_deploy(self, *, count: int = 2) -> ClusterInfo:
        """Start `count` nodes in one namespace and describe them.

        Raises before spawning anything if the host cannot do IPv6, since every
        node would fail the same way a few seconds later.
        """
        if count < 1:
            raise ValueError(f"Need at least one node, got {count}")
        if not ipv6_is_available():
            raise RuntimeError(
                "exo needs IPv6 to start: peer discovery joins an IPv6 multicast "
                "group and zenoh listens on tcp/[::]. This host cannot open an "
                "IPv6 socket. Loopback-only IPv6 is enough; enable it and retry."
            )
        if self._nodes:
            raise RuntimeError("This session already has nodes; call stop_all first")

        for index in range(count):
            name = f"local-{index}"
            ports = allocate_ports(index)
            node = LocalNode(
                name=name,
                ports=ports,
                log_path=self._log_dir / f"{name}.log",
                command=build_node_command(
                    ports,
                    self.namespace,
                    executable=self._executable,
                    offline=self._offline,
                ),
            )
            self._nodes[name] = node
            self._start(node)

        hosts = list(self._nodes)
        endpoints = {name: node.api_url for name, node in self._nodes.items()}
        return ClusterInfo(
            hosts=hosts,
            namespace=self.namespace,
            api_endpoints=endpoints,
            api_url=endpoints[hosts[0]],
            primary_host=hosts[0],
        )

    def _start(self, node: LocalNode) -> None:
        node.process = self._launcher(node.command, node.log_path, self._environment)

    def stop(self, hosts: Sequence[str], *, keep: bool = False) -> None:
        """Stop the named nodes.

        `keep` is accepted for parity with `EcoSession` and ignored: a local
        node holds no reservation to keep or release.
        """
        del keep
        for host in hosts:
            self._stop_node(self._require(host))

    def _stop_node(self, node: LocalNode) -> None:
        process = node.process
        if process is None or process.poll() is not None:
            node.process = None
            return
        # The child runs in its own session, so signal the whole group -
        # `uv run exo` is a wrapper and the node itself is its child.
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            _ = process.wait(timeout=STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                _ = process.wait(timeout=STOP_TIMEOUT_SECONDS)
        node.process = None

    def start_hosts(self, hosts: Sequence[str], *, namespace: str) -> None:
        """Restart previously stopped nodes into an existing namespace."""
        if namespace != self.namespace:
            raise ValueError(
                f"This session owns namespace {self.namespace!r}, not {namespace!r}"
            )
        for host in hosts:
            node = self._require(host)
            if node.is_running:
                continue
            self._start(node)

    def stop_all(self) -> None:
        for node in list(self._nodes.values()):
            with contextlib.suppress(Exception):
                self._stop_node(node)

    def release(self, hosts: Sequence[str]) -> None:
        """Stop the nodes and forget them. Local nodes reserve nothing."""
        self.stop(hosts)
        for host in hosts:
            _ = self._nodes.pop(host, None)

    def logs(self, hosts: Sequence[str], lines: int = 500) -> dict[str, list[str]]:
        """Tail each node's captured stdout and stderr."""
        collected: dict[str, list[str]] = {}
        for host in hosts:
            node = self._require(host)
            try:
                text = node.log_path.read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                collected[host] = [f"<could not read {node.log_path}: {error}>"]
                continue
            collected[host] = text.splitlines()[-lines:]
        return collected

    def exec(self, hosts: Sequence[str], command: str) -> str:
        """Not supported: every node is already on this machine.

        `EcoSession.exec` exists to reach across SSH. Locally there is nothing
        to reach, and silently running the command here would mean something
        different, so this refuses instead.
        """
        del hosts, command
        raise NotImplementedError(
            "LocalProcessSession has no remote hosts; run the command directly"
        )

    def _require(self, host: str) -> LocalNode:
        node = self._nodes.get(host)
        if node is None:
            raise KeyError(f"Unknown node {host!r}; known nodes: {sorted(self._nodes)}")
        return node

    def __enter__(self) -> "LocalProcessSession":
        return self

    def __exit__(self, *_exception: object) -> None:
        self.stop_all()


def main() -> int:
    """Start a local cluster and print its endpoints, for manual poking."""
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    log_dir = Path(os.environ.get("EXO_LOCAL_CLUSTER_LOGS", "/tmp/exo-local-cluster"))
    session = LocalProcessSession(log_dir=log_dir)
    cluster = session.start_deploy(count=count)
    print(f"namespace: {cluster.namespace}")
    for host, url in cluster.api_endpoints.items():
        print(f"  {host}: {url}")
    print(f"logs: {log_dir}")
    print("Press Ctrl-C to stop.")
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        session.stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
