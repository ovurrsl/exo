"""Run a multi-node exo cluster as local processes on a single host.

`EcoSession` deploys exo across real machines through the `eco` CLI, which is
not available outside the lab. `LocalProcessSession` offers the same surface
backed by several `exo` processes on one machine. That is enough to exercise
discovery, election, placement and the API, and it makes `disconnect_node` /
`reconnect_node` mean "stop and restart a process" rather than "power-cycle a
Mac".

Each node gets its own API and zenoh port and its own `EXO_HOME`, so nodes do
not share an event log, config or downloads. All nodes share one discovery
port and one namespace: discovery announces itself to an IPv6 multicast group
on the discovery port, so a node on a different port never hears the others.
The discovery socket is opened with SO_REUSEADDR (and SO_REUSEPORT on Unix), so
several nodes can bind it at once.

It is deliberately a sibling of `EcoSession` rather than a replacement: the two
answer different questions, and only a real deployment can tell you anything
about Thunderbolt, RDMA or Metal.

Requires IPv6. exo's peer discovery joins an IPv6 multicast group
(`rust/networking/src/discovery.rs`) and zenoh listens on `tcp/[::]`, so on a
host built without IPv6 support a node cannot start at all - loopback-only IPv6
is enough, a routable address is not needed.

Works on macOS, Linux and Windows. On Windows a node is started in its own
process group and stopped with CTRL_BREAK_EVENT, which exo handles as a
shutdown request, then with `taskkill /T /F` if it does not exit in time.
"""

from __future__ import annotations

import atexit
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from http.client import HTTPResponse
from pathlib import Path
from typing import Protocol, cast

from .cluster import ClusterInfo

__all__ = [
    "LocalNode",
    "LocalProcessSession",
    "NodeProcess",
    "PortAllocation",
    "allocate_ports",
    "build_node_command",
    "build_node_environment",
    "count_visible_nodes",
    "ipv6_is_available",
]

# exo's own defaults, so a single-node local session looks like a plain
# `uv run exo` to anything reading the API.
DEFAULT_API_PORT = 52415
DEFAULT_ZENOH_PORT = 52414
DEFAULT_DISCOVERY_PORT = 52413

# Each node claims a contiguous block, so node N never collides with node N+1
# no matter which of the two per-node ports moves first.
PORT_STRIDE = 10

STOP_TIMEOUT_SECONDS = 20.0
READY_POLL_SECONDS = 1.0


@dataclass(frozen=True)
class PortAllocation:
    """The ports one local node listens on.

    `discovery` is the same for every node of a session; see the module
    docstring.
    """

    api: int
    zenoh: int
    discovery: int


def allocate_ports(
    index: int, *, discovery_port: int = DEFAULT_DISCOVERY_PORT
) -> PortAllocation:
    """Ports for the node at `index`, counting from zero.

    Pure so a test can assert the layout without binding anything.
    """
    if index < 0:
        raise ValueError(f"Node index must not be negative: {index}")
    offset = index * PORT_STRIDE
    return PortAllocation(
        api=DEFAULT_API_PORT + offset,
        zenoh=DEFAULT_ZENOH_PORT + offset,
        discovery=discovery_port,
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


def build_node_environment(base: Mapping[str, str], exo_home: Path) -> dict[str, str]:
    """The environment for one node: `base` with the node's own `EXO_HOME`.

    exo reads `EXO_HOME` relative to the home directory, so an absolute path
    is passed. Model directories set in `base` (`EXO_DEFAULT_MODELS_DIR`,
    `EXO_MODELS_READ_ONLY_DIRS`) are kept, so a caller can point every node
    at models that are already downloaded.
    """
    environment = dict(base)
    environment["EXO_HOME"] = str(exo_home.resolve())
    return environment


def count_visible_nodes(api_url: str, timeout: float = 5.0) -> int | None:
    """How many nodes `api_url`'s node sees with memory reported, or `None`
    if its API does not answer yet.

    Placement needs memory for every node, so a node only counts once it has
    reported it - the same rule as `harness.wait_for_cluster_ready`.
    """
    try:
        response = cast(
            HTTPResponse,
            urllib.request.urlopen(f"{api_url}/state", timeout=timeout),
        )
        with response:
            body = response.read()
        state: object = json.loads(body)  # pyright: ignore[reportAny]
    except (OSError, ValueError):
        # URLError is an OSError; a half-started API can answer with junk.
        return None
    if not isinstance(state, dict):
        return None
    fields = cast(dict[str, object], state)
    counts = [
        len(cast(dict[str, object], value))
        for value in (fields.get("nodeIdentities"), fields.get("nodeMemory"))
        if isinstance(value, dict)
    ]
    return min(counts) if len(counts) == 2 else 0


class NodeProcess(Protocol):
    """What the session needs from a started node."""

    def poll(self) -> int | None: ...

    def wait(self, timeout: float) -> int: ...

    def request_stop(self) -> None:
        """Ask the node and its children to shut down."""
        ...

    def force_stop(self) -> None:
        """Kill the node and its children."""
        ...


@dataclass
class LocalNode:
    """One exo process, and everything needed to restart it unchanged."""

    name: str
    ports: PortAllocation
    log_path: Path
    exo_home: Path
    command: list[str]
    process: NodeProcess | None = field(default=None, repr=False)

    @property
    def api_url(self) -> str:
        return f"http://127.0.0.1:{self.ports.api}"

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


# Injected so tests can drive the lifecycle without starting real processes.
Launcher = Callable[[Sequence[str], Path, Mapping[str, str]], NodeProcess]


class _SpawnedNode:
    """A real node process.

    `uv run exo` is a wrapper and the node itself is its child, so stopping
    has to reach the whole process tree: a process group on Unix, a console
    process group plus `taskkill /T` on Windows.
    """

    def __init__(self, popen: subprocess.Popen[bytes]) -> None:
        self._popen = popen

    def poll(self) -> int | None:
        return self._popen.poll()

    def wait(self, timeout: float) -> int:
        return self._popen.wait(timeout=timeout)

    def request_stop(self) -> None:
        if sys.platform == "win32":
            with contextlib.suppress(OSError):
                self._popen.send_signal(signal.CTRL_BREAK_EVENT)
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(self._popen.pid, signal.SIGTERM)

    def force_stop(self) -> None:
        if sys.platform == "win32":
            with contextlib.suppress(OSError):
                _ = subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(self._popen.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(self._popen.pid, signal.SIGKILL)


def _spawn(
    command: Sequence[str], log_path: Path, environment: Mapping[str, str]
) -> NodeProcess:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        if sys.platform == "win32":
            popen = subprocess.Popen(
                list(command),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=dict(environment),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            # A new session makes the node the leader of its own process
            # group, whose id is its pid.
            popen = subprocess.Popen(
                list(command),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=dict(environment),
                start_new_session=True,
            )
    return _SpawnedNode(popen)


# Probes how many nodes an API sees; injected so tests need no HTTP server.
ReadinessProbe = Callable[[str], "int | None"]


class LocalProcessSession:
    """`EcoSession`'s surface, backed by local processes.

    Host names are synthetic (`local-0`, `local-1`, ...) unless given, and are
    what the `ClusterInfo` returned by `start_deploy` is keyed on, so the
    existing test framework's `disconnect_node(index)` addresses them
    unchanged.

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
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        launcher: Launcher = _spawn,
        readiness_probe: ReadinessProbe = count_visible_nodes,
        install_signal_handlers: bool = True,
    ) -> None:
        self._session_id = uuid.uuid4().hex[:8]
        self.namespace = namespace or f"local-{self._session_id}"
        self._log_dir = log_dir
        self._offline = offline
        self._executable = tuple(executable)
        self._environment = dict(environment if environment is not None else os.environ)
        self._discovery_port = discovery_port
        self._launcher = launcher
        self._readiness_probe = readiness_probe
        self._nodes: dict[str, LocalNode] = {}

        atexit.register(self.stop_all)
        if install_signal_handlers:
            # SIGHUP does not exist on Windows.
            for name in ("SIGTERM", "SIGHUP"):
                signal_number: signal.Signals | None = getattr(signal, name, None)
                if signal_number is None:
                    continue
                with contextlib.suppress(ValueError):
                    _ = signal.signal(signal_number, self._signal_handler)

    def _signal_handler(self, signum: int, _frame: object) -> None:
        self.stop_all()
        raise SystemExit(128 + signum)

    @property
    def nodes(self) -> Mapping[str, LocalNode]:
        return self._nodes

    def start_deploy(
        self,
        hosts: Sequence[str] | None = None,
        *,
        count: int | None = None,
        wait: bool = True,
        timeout: float = 600,
    ) -> ClusterInfo:
        """Start nodes in one namespace and describe them.

        Takes `EcoSession.start_deploy`'s arguments that mean something
        locally: `hosts` names the nodes (default `local-0` ... ), `count` is
        how many to start when `hosts` is not given (default 2), and with
        `wait` this returns only once every node sees all the others, like
        `eco start --wait`.

        Raises before spawning anything if the host cannot do IPv6, since every
        node would fail the same way a few seconds later.
        """
        names = (
            list(hosts)
            if hosts
            else [f"local-{index}" for index in range(2 if count is None else count)]
        )
        if count is not None and hosts and count != len(names):
            raise ValueError(f"Got {len(names)} hosts but count={count}")
        if not names:
            raise ValueError("Need at least one node")
        if len(set(names)) != len(names):
            raise ValueError(f"Host names must be unique: {names}")
        if not ipv6_is_available():
            raise RuntimeError(
                "exo needs IPv6 to start: peer discovery joins an IPv6 multicast "
                "group and zenoh listens on tcp/[::]. This host cannot open an "
                "IPv6 socket. Loopback-only IPv6 is enough; enable it and retry."
            )
        if self._nodes:
            raise RuntimeError("This session already has nodes; call stop_all first")

        for index, name in enumerate(names):
            ports = allocate_ports(index, discovery_port=self._discovery_port)
            node = LocalNode(
                name=name,
                ports=ports,
                log_path=self._log_dir / f"{name}.log",
                exo_home=self._log_dir / name / "exo-home",
                command=build_node_command(
                    ports,
                    self.namespace,
                    executable=self._executable,
                    offline=self._offline,
                ),
            )
            self._nodes[name] = node
            self._start(node)

        endpoints = {name: node.api_url for name, node in self._nodes.items()}
        if wait:
            self.wait_until_ready(names, timeout=timeout)
        return ClusterInfo(
            hosts=names,
            namespace=self.namespace,
            api_endpoints=endpoints,
            api_url=endpoints[names[0]],
            primary_host=names[0],
        )

    def wait_until_ready(self, hosts: Sequence[str], *, timeout: float) -> None:
        """Wait until every named node sees all of them with memory reported.

        Fails early, with the log tail, if a node exits while waiting.
        """
        nodes = [self._require(host) for host in hosts]
        deadline = time.monotonic() + timeout
        while True:
            for node in nodes:
                process = node.process
                exit_code = None if process is None else process.poll()
                if process is None or exit_code is not None:
                    tail = "\n".join(self.logs([node.name], lines=20)[node.name])
                    raise RuntimeError(
                        f"Node {node.name} exited (code {exit_code}) before the "
                        f"cluster was ready. Last log lines:\n{tail}"
                    )
            if all(
                (self._readiness_probe(node.api_url) or 0) >= len(nodes)
                for node in nodes
            ):
                return
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Nodes {list(hosts)} did not all see each other within "
                    f"{timeout}s; logs are in {self._log_dir}"
                )
            time.sleep(READY_POLL_SECONDS)

    def _start(self, node: LocalNode) -> None:
        node.exo_home.mkdir(parents=True, exist_ok=True)
        node.process = self._launcher(
            node.command,
            node.log_path,
            build_node_environment(self._environment, node.exo_home),
        )

    def stop(
        self, hosts: Sequence[str], *, keep: bool = False, timeout: float = 120
    ) -> None:
        """Stop the named nodes.

        `keep` and `timeout` are accepted for parity with `EcoSession` and
        ignored: a local node holds no reservation, and each node gets
        `STOP_TIMEOUT_SECONDS` to exit before it is killed.
        """
        del keep, timeout
        for host in hosts:
            self._stop_node(self._require(host))

    def _stop_node(self, node: LocalNode) -> None:
        process = node.process
        node.process = None
        if process is None or process.poll() is not None:
            return
        process.request_stop()
        try:
            _ = process.wait(timeout=STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.force_stop()
            with contextlib.suppress(subprocess.TimeoutExpired):
                _ = process.wait(timeout=STOP_TIMEOUT_SECONDS)

    def start_hosts(
        self, hosts: Sequence[str], *, namespace: str, timeout: float = 300
    ) -> None:
        """Restart previously stopped nodes into an existing namespace.

        Like `eco start`, this does not wait for the nodes to rejoin; call
        `wait_until_ready` for that.
        """
        del timeout
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

    def release(self, hosts: Sequence[str], timeout: float = 120) -> None:
        """Stop the nodes and forget them. Local nodes reserve nothing."""
        self.stop(hosts, timeout=timeout)
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

    def exec(self, hosts: Sequence[str], command: str, timeout: float = 120) -> str:
        """Not supported: every node is already on this machine.

        `EcoSession.exec` exists to reach across SSH. Locally there is nothing
        to reach, and silently running the command here would mean something
        different, so this refuses instead.
        """
        del hosts, command, timeout
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
    log_dir = Path(
        os.environ.get(
            "EXO_LOCAL_CLUSTER_LOGS",
            str(Path(tempfile.gettempdir()) / "exo-local-cluster"),
        )
    )
    session = LocalProcessSession(log_dir=log_dir)
    try:
        cluster = session.start_deploy(count=count)
        print(f"namespace: {cluster.namespace}")
        for host, url in cluster.api_endpoints.items():
            print(f"  {host}: {url}")
        print(f"logs: {log_dir}")
        print("Press Ctrl-C to stop.")
        # signal.pause() does not exist on Windows.
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        session.stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
