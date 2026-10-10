"""Package staging must reject drift without invoking CUDA or an installer."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

VALIDATOR = Path(__file__).resolve().parents[1] / "validate_runtime.py"


def runtime(tmp_path: Path) -> Path:
    root = tmp_path / "Türkçe runtime"
    root.mkdir()
    files = {
        "exo.exe": b"exe",
        "_internal/cuda.dll": b"cuda",
        "_internal/headers/kernel.h": b"header",
        "dashboard/index.html": b"html",
    }
    for name, contents in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    hashes = {
        name: hashlib.sha256(contents).hexdigest() for name, contents in files.items()
    }
    manifest = {
        "schema": 2,
        "file_sha256": hashes,
        "binary_sha256": {
            name: digest
            for name, digest in hashes.items()
            if Path(name).suffix in {".exe", ".dll"}
        },
        "runtime_gates": {
            "passed": True,
            "frozen": True,
            "device": "gpu",
            "results": [
                {"check": "example", "pass": True, "exit_code": 7, "expected": 7}
            ],
        },
    }
    (root / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def validate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--runtime", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_complete_runtime_is_accepted(tmp_path: Path) -> None:
    result = validate(runtime(tmp_path))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "name",
    [
        "exo.exe",
        "_internal/cuda.dll",
        "_internal/headers/kernel.h",
        "dashboard/index.html",
    ],
)
def test_modified_runtime_file_is_rejected(tmp_path: Path, name: str) -> None:
    root = runtime(tmp_path)
    (root / name).write_bytes(b"changed after GPU gate")
    result = validate(root)
    assert result.returncode != 0
    assert "hash mismatch" in result.stderr


def test_extra_native_library_is_rejected(tmp_path: Path) -> None:
    root = runtime(tmp_path)
    (root / "_internal/unreviewed.dll").write_bytes(b"unreviewed")
    result = validate(root)
    assert result.returncode != 0
    assert "file set differs" in result.stderr


@pytest.mark.parametrize(
    "name", ["../outside.dll", "C:/outside.dll", "_internal/../exo.exe"]
)
def test_manifest_path_escape_is_rejected(tmp_path: Path, name: str) -> None:
    root = runtime(tmp_path)
    path = root / "runtime-manifest.json"
    manifest = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    hashes = cast(dict[str, str], manifest["file_sha256"])
    hashes[name] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate(root)
    assert result.returncode != 0
    assert "invalid manifest path" in result.stderr


def test_failed_individual_gate_is_rejected(tmp_path: Path) -> None:
    root = runtime(tmp_path)
    path = root / "runtime-manifest.json"
    manifest = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    gates = cast(dict[str, object], manifest["runtime_gates"])
    results = cast(list[dict[str, object]], gates["results"])
    results[0]["pass"] = False
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate(root)
    assert result.returncode != 0
    assert "individual runtime gate failed" in result.stderr
