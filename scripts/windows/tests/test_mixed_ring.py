"""Physical acceptance must reject mismatched peers and partial success."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check_mixed_ring.py"


class Checker(Protocol):
    MAC_BASELINE: str
    MAC_MLX: str

    def validate_peer(
        self, peer: dict[str, object], expected: dict[str, str]
    ) -> None: ...

    def rank_passed(self, exit_code: int, text: str, rank: int) -> bool: ...

    def read_record(self, text: str, marker: str) -> dict[str, object]: ...

    def stop_owned(self, process: subprocess.Popen[bytes]) -> None: ...


def checker() -> Checker:
    spec = importlib.util.spec_from_file_location("mixed_ring_checker", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Checker, cast(object, module))


def test_wrong_mac_baseline_is_rejected() -> None:
    module = checker()
    with pytest.raises(ValueError, match="Mac commit"):
        module.validate_peer({"commit": "0" * 40}, {})


def test_changed_protocol_source_is_rejected() -> None:
    module = checker()
    with pytest.raises(ValueError, match="source mismatch"):
        module.validate_peer(
            {"commit": module.MAC_BASELINE, "sources": {"cache.py": "b"}},
            {"cache.py": "a"},
        )


def test_mac_without_real_metal_compute_is_rejected() -> None:
    module = checker()
    with pytest.raises(ValueError, match="Metal"):
        module.validate_peer(
            {
                "commit": module.MAC_BASELINE,
                "sources": {},
                "system": "Darwin",
                "machine": "arm64",
                "mlx": module.MAC_MLX,
                "ring": True,
                "gpu_value": None,
            },
            {},
        )


def metal_peer(version: str) -> dict[str, object]:
    return {
        "commit": checker().MAC_BASELINE,
        "sources": {},
        "system": "Darwin",
        "machine": "arm64",
        "mlx": version,
        "mlx_source": {
            "url": "https://github.com/rltakashige/mlx-jaccl-fix-small-recv.git",
            "vcs_info": {
                "vcs": "git",
                "commit_id": "cc3f3e60be1289506125f2fa19b73b05aa770df8",
            },
        },
        "ring": True,
        "gpu_value": 16,
    }


def test_same_pinned_mac_commit_built_on_another_date_is_accepted() -> None:
    checker().validate_peer(metal_peer("0.32.0.dev20261010+cc3f3e60"), {})


@pytest.mark.parametrize(
    "source",
    [
        None,
        {
            "url": "https://example.invalid/mlx.git",
            "vcs_info": {
                "vcs": "git",
                "commit_id": "cc3f3e60be1289506125f2fa19b73b05aa770df8",
            },
        },
        {
            "url": "https://github.com/rltakashige/mlx-jaccl-fix-small-recv.git",
            "vcs_info": {"vcs": "git", "commit_id": "0" * 40},
        },
    ],
)
def test_version_label_alone_does_not_prove_pinned_mac_source(source: object) -> None:
    peer = metal_peer(checker().MAC_MLX)
    peer["mlx_source"] = source
    with pytest.raises(ValueError, match="MLX source"):
        checker().validate_peer(peer, {})


@pytest.mark.parametrize(
    "version", ["0.32.3.dev20261010+cc3f3e60", "0.32.0.dev20261010+deadbeef", "0.32.0"]
)
def test_other_mac_mlx_versions_are_rejected(version: str) -> None:
    with pytest.raises(ValueError):
        checker().validate_peer(metal_peer(version), {})


def test_exit_zero_does_not_pass_a_rank() -> None:
    assert checker().rank_passed(0, "rank 0 ring complete\n", 0) is False


def test_missing_collectives_do_not_pass_a_rank() -> None:
    assert checker().rank_passed(7, "rank 0 ring complete\n", 0) is False


def test_wrong_rank_output_is_rejected() -> None:
    text = (
        "\n".join(
            f"ring 1 2 mlx.core.{dtype} {length} collectives passed"
            for dtype in ("float32", "float16", "bfloat16", "int32")
            for length in (4096, 2097153)
        )
        + "\nrank 1 ring complete\n"
    )
    assert checker().rank_passed(7, text, 0) is False
    assert checker().rank_passed(7, text, 1) is True


def test_shell_metacharacters_in_target_are_rejected_before_ssh() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ssh-target",
            "user;echo bad@192.168.1.105",
            "--pc-ip",
            "192.168.1.101",
            "--ssh-key",
            "missing-key",
            "--known-hosts",
            "missing-hosts",
            "--output",
            "unused-output",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "SSH target must be user@IPv4" in result.stderr


@pytest.mark.parametrize("text", ["", "RESULT {}\nRESULT {}\n", "RESULT []\n"])
def test_missing_duplicate_and_nonobject_remote_results_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        checker().read_record(text, "RESULT ")


def test_cleanup_does_not_kill_an_unrelated_process() -> None:
    command = [sys.executable, "-c", "import time; time.sleep(60)"]
    with subprocess.Popen(command) as unrelated, subprocess.Popen(command) as owned:
        try:
            checker().stop_owned(owned)
            assert owned.poll() is not None
            assert unrelated.poll() is None
        finally:
            unrelated.terminate()
            _ = unrelated.wait(timeout=5)
            if owned.poll() is None:
                owned.kill()
                _ = owned.wait(timeout=5)
