"""Tests for the local-process cluster session.

Every test here drives the lifecycle through an injected launcher, so nothing
spawns an exo node, binds a port, or needs IPv6. What is under test is the
bookkeeping: which ports each node gets, what argv it is started with, and that
stop/start/release leave the session in the state the test framework expects.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from exo_tools.local_cluster import (
    DEFAULT_API_PORT,
    DEFAULT_DISCOVERY_PORT,
    DEFAULT_ZENOH_PORT,
    PORT_STRIDE,
    LocalProcessSession,
    allocate_ports,
    build_node_command,
)


class FakeProcess:
    """Stands in for Popen: records signals instead of receiving them."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self._returncode: int | None = None

    def poll(self) -> int | None:
        return self._returncode

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self._returncode is None:
            self._returncode = 0
        return self._returncode


class RecordingLauncher:
    """Captures every spawn so a test can assert on argv and ordering."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path]] = []
        self._next_pid = 1000

    def __call__(
        self,
        command: Sequence[str],
        log_path: Path,
        environment: Mapping[str, str],
    ) -> subprocess.Popen[bytes]:
        del environment
        self.calls.append((list(command), log_path))
        self._next_pid += 1
        # The session only uses poll/wait/pid, which FakeProcess provides.
        return FakeProcess(self._next_pid)  # pyright: ignore[reportReturnType]


def _session(tmp_path: Path, launcher: RecordingLauncher) -> LocalProcessSession:
    return LocalProcessSession(
        log_dir=tmp_path,
        namespace="test-namespace",
        launcher=launcher,
    )


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
        assert max(current.api, current.zenoh, current.discovery) < min(
            following.api, following.zenoh, following.discovery
        )
    assert allocate_ports(3).api - allocate_ports(2).api == PORT_STRIDE


def test_allocate_ports_rejects_negative_index() -> None:
    with pytest.raises(ValueError):
        _ = allocate_ports(-1)


def test_build_node_command_passes_every_port_and_namespace() -> None:
    command = build_node_command(allocate_ports(1), "ns")
    assert command[:3] == ["uv", "run", "exo"]
    for flag, value in (
        ("--api-port", str(DEFAULT_API_PORT + PORT_STRIDE)),
        ("--zenoh-port", str(DEFAULT_ZENOH_PORT + PORT_STRIDE)),
        ("--discovery-port", str(DEFAULT_DISCOVERY_PORT + PORT_STRIDE)),
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


def test_start_deploy_starts_one_process_per_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)

    cluster = session.start_deploy(count=3)

    assert len(launcher.calls) == 3
    assert cluster.hosts == ["local-0", "local-1", "local-2"]
    assert cluster.namespace == "test-namespace"
    assert cluster.api_url == f"http://127.0.0.1:{DEFAULT_API_PORT}"
    # All three must share one namespace or they will not discover each other.
    for command, _ in launcher.calls:
        assert command[command.index("--namespace") + 1] == "test-namespace"


def test_start_deploy_refuses_without_ipv6(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail up front, not several seconds later inside zenoh."""
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: False)
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)

    with pytest.raises(RuntimeError, match="IPv6"):
        _ = session.start_deploy(count=2)

    assert launcher.calls == []


def test_disconnect_and_reconnect_reuses_the_same_ports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reconnected node must rejoin as itself, not as a new node."""
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)
    _ = session.start_deploy(count=2)
    original_command = launcher.calls[1][0]

    session.stop(["local-1"], keep=True)
    assert not session.nodes["local-1"].is_running

    session.start_hosts(["local-1"], namespace="test-namespace")

    assert session.nodes["local-1"].is_running
    assert launcher.calls[-1][0] == original_command


def test_start_hosts_is_idempotent_for_a_running_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    launcher = RecordingLauncher()
    session = _session(tmp_path, launcher)
    _ = session.start_deploy(count=1)

    session.start_hosts(["local-0"], namespace="test-namespace")

    assert len(launcher.calls) == 1


def test_start_hosts_rejects_a_foreign_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=1)

    with pytest.raises(ValueError, match="namespace"):
        session.start_hosts(["local-0"], namespace="someone-elses")


def test_release_forgets_the_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=2)

    session.release(["local-1"])

    assert "local-1" not in session.nodes
    with pytest.raises(KeyError):
        session.stop(["local-1"])


def test_stop_all_stops_every_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=3)

    session.stop_all()

    assert all(not node.is_running for node in session.nodes.values())


def test_logs_tails_each_nodes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=1)
    (tmp_path / "local-0.log").write_text("\n".join(f"line {n}" for n in range(10)))

    assert session.logs(["local-0"], lines=3) == {
        "local-0": ["line 7", "line 8", "line 9"]
    }


def test_logs_reports_a_missing_file_instead_of_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=1)

    collected = session.logs(["local-0"])

    assert "could not read" in collected["local-0"][0]


def test_exec_refuses_rather_than_running_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=1)

    with pytest.raises(NotImplementedError):
        _ = session.exec(["local-0"], "echo hi")


def test_unknown_host_names_the_known_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exo_tools.local_cluster.ipv6_is_available", lambda: True)
    session = _session(tmp_path, RecordingLauncher())
    _ = session.start_deploy(count=2)

    with pytest.raises(KeyError, match="local-0"):
        session.stop(["nope"])
