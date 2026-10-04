"""Tests for the local-process cluster session.

Every test here drives the lifecycle through an injected launcher and readiness
probe, so nothing spawns an exo node, binds a port, or needs IPv6. What is under test is the
bookkeeping: which ports each node gets, what argv it is started with, and that
stop/start/release leave the session in the state the test framework expects.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
from exo_tools.local_cluster import (
    DEFAULT_API_PORT,
    DEFAULT_DISCOVERY_PORT,
    DEFAULT_ZENOH_PORT,
    PORT_STRIDE,
    LocalProcessSession,
    NodeProcess,
    allocate_ports,
    build_node_command,
)


class FakeProcess:
    """Stands in for a node process: records stop requests instead of signals."""

    def __init__(self, *, ignores_stop: bool = False) -> None:
        self.returncode: int | None = None
        self.stop_requests = 0
        self.force_stops = 0
        self._ignores_stop = ignores_stop

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float) -> int:
        if self.returncode is None:
            raise subprocess.TimeoutExpired("exo", timeout)
        return self.returncode

    def request_stop(self) -> None:
        self.stop_requests += 1
        if not self._ignores_stop:
            self.returncode = 0

    def force_stop(self) -> None:
        self.force_stops += 1
        self.returncode = -9


class RecordingLauncher:
    """Captures every spawn so a test can assert on argv, environment and order."""

    def __init__(self, *, ignores_stop: bool = False) -> None:
        self.calls: list[tuple[list[str], Path, dict[str, str]]] = []
        self.processes: list[FakeProcess] = []
        self._ignores_stop = ignores_stop

    def __call__(
        self,
        command: Sequence[str],
        log_path: Path,
        environment: Mapping[str, str],
    ) -> NodeProcess:
        self.calls.append((list(command), log_path, dict(environment)))
        process = FakeProcess(ignores_stop=self._ignores_stop)
        self.processes.append(process)
        return process


def _session(
    tmp_path: Path,
    launcher: RecordingLauncher,
    readiness_probe: Callable[[str], int | None] = lambda _url: None,
) -> LocalProcessSession:
    return LocalProcessSession(
        log_dir=tmp_path,
        namespace="test-namespace",
        environment={"PATH": "/usr/bin"},
        launcher=launcher,
        readiness_probe=readiness_probe,
        install_signal_handlers=False,
    )


@pytest.fixture(autouse=True)
def pretend_ipv6_and_skip_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    # Readiness polling would otherwise sleep between probes.
    monkeypatch.setattr("exo_tools.local_cluster.READY_POLL_SECONDS", 0.0)
    monkeypatch.setattr("exo_tools.local_cluster.STOP_TIMEOUT_SECONDS", 0.0)


def test_allocate_ports_starts_at_exo_defaults() -> None:
    """Node zero must look exactly like a plain `uv run exo`."""
    ports = allocate_ports(0)
    assert ports.api == DEFAULT_API_PORT
    assert ports.zenoh == DEFAULT_ZENOH_PORT
    assert ports.discovery == DEFAULT_DISCOVERY_PORT


def test_allocate_ports_blocks_do_not_overlap() -> None:
    """Every port of node N must be below every port of node N+1."""
    for index in range(8):
        current = allocate_ports(index)
        following = allocate_ports(index + 1)
        assert max(current.api, current.zenoh) < min(following.api, following.zenoh)
    assert allocate_ports(3).api - allocate_ports(2).api == PORT_STRIDE


def test_allocate_ports_shares_the_discovery_port() -> None:
    """Discovery multicasts to one port; a node on another port hears nothing."""
    ports = [allocate_ports(index) for index in range(8)]
    assert {p.discovery for p in ports} == {DEFAULT_DISCOVERY_PORT}
    assert all(DEFAULT_DISCOVERY_PORT not in (p.api, p.zenoh) for p in ports)
    assert allocate_ports(2, discovery_port=40000).discovery == 40000


def test_allocate_ports_rejects_negative_index() -> None:
    with pytest.raises(ValueError):
        _ = allocate_ports(-1)


def test_build_node_command_passes_every_port_and_namespace() -> None:
    command = build_node_command(allocate_ports(1), "ns")
    assert command[:3] == ["uv", "run", "exo"]
    for flag, value in (
        ("--api-port", str(DEFAULT_API_PORT + PORT_STRIDE)),
        ("--zenoh-port", str(DEFAULT_ZENOH_PORT + PORT_STRIDE)),
        ("--discovery-port", str(DEFAULT_DISCOVERY_PORT)),
        ("--namespace", "ns"),
    ):
        assert command[command.index(flag) + 1] == value
    assert "--offline" not in command


def test_build_node_command_offline_and_extra_arguments() -> None:
    command = build_node_command(
        allocate_ports(0), "ns", offline=True, extra_arguments=("--no-batch",)
    )
    assert "--offline" in command
    assert command[-1] == "--no-batch"


def test_start_deploy_starts_one_process_per_node(tmp_path: Path) -> None:
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)

    cluster = session.start_deploy(count=3, wait=False)

    assert len(launcher.calls) == 3
    assert cluster.hosts == ["local-0", "local-1", "local-2"]
    assert cluster.namespace == "test-namespace"
    assert cluster.api_url == f"http://127.0.0.1:{DEFAULT_API_PORT}"
    # All three must share one namespace or they will not discover each other.
    for command, _, _ in launcher.calls:
        assert command[command.index("--namespace") + 1] == "test-namespace"


def test_start_deploy_refuses_without_ipv6(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail up front, not several seconds later inside zenoh."""
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: False)
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)

    with pytest.raises(RuntimeError, match="IPv6"):
        _ = session.start_deploy(count=2, wait=False)

    assert launcher.calls == []


def test_disconnect_and_reconnect_reuses_the_same_ports(tmp_path: Path) -> None:
    """A reconnected node must rejoin as itself, not as a new node."""
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)
    _ = session.start_deploy(count=2, wait=False)
    original_command = launcher.calls[1][0]

    session.stop(["local-1"], keep=True)
    assert not session.nodes["local-1"].is_running

    session.start_hosts(["local-1"], namespace="test-namespace")

    assert session.nodes["local-1"].is_running
    assert launcher.calls[-1][0] == original_command


def test_start_hosts_is_idempotent_for_a_running_node(tmp_path: Path) -> None:
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)
    _ = session.start_deploy(count=1, wait=False)

    session.start_hosts(["local-0"], namespace="test-namespace")

    assert len(launcher.calls) == 1


def test_start_hosts_rejects_a_foreign_namespace(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=1, wait=False)

    with pytest.raises(ValueError, match="namespace"):
        session.start_hosts(["local-0"], namespace="someone-elses")


def test_release_forgets_the_node(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=2, wait=False)

    session.release(["local-1"])

    assert "local-1" not in session.nodes
    with pytest.raises(KeyError):
        session.stop(["local-1"])


def test_stop_all_stops_every_node(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=3, wait=False)

    session.stop_all()

    assert all(not node.is_running for node in session.nodes.values())


def test_logs_tails_each_nodes_file(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=1, wait=False)
    (tmp_path / "local-0.log").write_text("\n".join(f"line {n}" for n in range(10)))

    assert session.logs(["local-0"], lines=3) == {
        "local-0": ["line 7", "line 8", "line 9"]
    }


def test_logs_reports_a_missing_file_instead_of_raising(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=1, wait=False)

    collected = session.logs(["local-0"])

    assert "could not read" in collected["local-0"][0]


def test_exec_refuses_rather_than_running_locally(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=1, wait=False)

    with pytest.raises(NotImplementedError):
        _ = session.exec(["local-0"], "echo hi")


def test_unknown_host_names_the_known_ones(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=2, wait=False)

    with pytest.raises(KeyError, match="local-0"):
        session.stop(["nope"])


def test_each_node_gets_its_own_exo_home(tmp_path: Path) -> None:
    """Nodes sharing EXO_HOME would share an event log, config and downloads."""
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)
    _ = session.start_deploy(count=2, wait=False)

    homes = [environment["EXO_HOME"] for _, _, environment in launcher.calls]

    assert len(set(homes)) == 2
    for home in homes:
        assert Path(home).is_absolute()
        assert Path(home).is_dir()
    # The rest of the caller's environment is passed through.
    assert all(env["PATH"] == "/usr/bin" for _, _, env in launcher.calls)


def test_a_restarted_node_keeps_its_exo_home(tmp_path: Path) -> None:
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)
    _ = session.start_deploy(count=2, wait=False)
    original_home = launcher.calls[1][2]["EXO_HOME"]

    session.stop(["local-1"])
    session.start_hosts(["local-1"], namespace="test-namespace")

    assert launcher.calls[-1][2]["EXO_HOME"] == original_home


def test_start_deploy_takes_host_names(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher())

    cluster = session.start_deploy(["a", "b"], wait=False)

    assert cluster.hosts == ["a", "b"]
    assert cluster.primary_host == "a"
    assert sorted(session.nodes) == ["a", "b"]


def test_start_deploy_rejects_a_count_that_does_not_match_the_hosts(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path, RecordingLauncher())

    with pytest.raises(ValueError, match="count"):
        _ = session.start_deploy(["a", "b"], count=3, wait=False)


def test_start_deploy_waits_until_every_node_sees_the_others(
    tmp_path: Path,
) -> None:
    probes: list[str] = []

    def probe(api_url: str) -> int | None:
        probes.append(api_url)
        # Nothing answers at first, then one node, then both see both.
        return [None, None, 1, 1, 2, 2][min(len(probes) - 1, 5)]

    session = _session(tmp_path, RecordingLauncher(), readiness_probe=probe)

    _ = session.start_deploy(count=2, timeout=60)

    assert len(probes) == 6


def test_start_deploy_times_out_when_nodes_never_meet(tmp_path: Path) -> None:
    session = _session(tmp_path, RecordingLauncher(), readiness_probe=lambda _: 1)

    with pytest.raises(TimeoutError):
        _ = session.start_deploy(count=2, timeout=0)


def test_start_deploy_reports_a_node_that_exits_while_waiting(
    tmp_path: Path,
) -> None:
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)
    (tmp_path / "local-1.log").write_text("Address already in use\n")

    def probe(_api_url: str) -> int | None:
        launcher.processes[1].returncode = 1
        return None

    session._readiness_probe = probe  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(RuntimeError, match="Address already in use"):
        _ = session.start_deploy(count=2, timeout=60)


def test_stop_asks_first_and_kills_only_a_node_that_ignores_it(
    tmp_path: Path,
) -> None:
    launcher = RecordingLauncher(ignores_stop=True)
    session = _session(tmp_path, launcher)
    _ = session.start_deploy(count=1, wait=False)

    session.stop(["local-0"])

    process = launcher.processes[0]
    assert process.stop_requests == 1
    assert process.force_stops == 1
    assert not session.nodes["local-0"].is_running


def test_stop_does_not_kill_a_node_that_exits_when_asked(tmp_path: Path) -> None:
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)
    _ = session.start_deploy(count=1, wait=False)

    session.stop(["local-0"])

    assert launcher.processes[0].stop_requests == 1
    assert launcher.processes[0].force_stops == 0
