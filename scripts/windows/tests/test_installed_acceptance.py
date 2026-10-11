"""Consumer acceptance must reject stale binaries without launching the engine."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows acceptance")
SCRIPT = Path(__file__).resolve().parents[1] / "check-installed-runtime.ps1"


def candidate(tmp_path: Path) -> tuple[Path, Path, Path]:
    runtime = tmp_path / "Türkçe runtime"
    runtime.mkdir()
    executable = runtime / "exo.exe"
    executable.write_bytes(b"preflight must not execute this file")
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    (runtime / "runtime-manifest.json").write_text(
        json.dumps(
            {
                "schema": 2,
                "file_sha256": {"exo.exe": digest},
                "binary_sha256": {"exo.exe": digest},
            }
        ),
        encoding="utf-8",
    )
    models = tmp_path / "read-only-models"
    models.mkdir()
    return runtime, models, tmp_path / "new-evidence"


def preflight(
    runtime: Path, models: Path, output: Path
) -> subprocess.CompletedProcess[str]:
    shell = shutil.which("pwsh")
    assert shell is not None
    return subprocess.run(
        [
            shell,
            "-NoProfile",
            "-File",
            str(SCRIPT),
            "-RuntimeDirectory",
            str(runtime),
            "-ModelDirectory",
            str(models),
            "-OutputDirectory",
            str(output),
            "-AllowDeveloperMachine",
            "-PreflightOnly",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_preflight_does_not_claim_hardware_or_clean_machine_acceptance(
    tmp_path: Path,
) -> None:
    runtime, models, output = candidate(tmp_path)
    result = preflight(runtime, models, output)
    assert result.returncode == 0, result.stderr
    report = TypeAdapter(dict[str, JsonValue]).validate_json(
        (output / "installed-runtime.json").read_text(encoding="utf-8-sig")
    )
    assert report["preflight_passed"] is True
    assert report["passed"] is False
    assert report["clean_windows_acceptance_passed"] is False
    assert report["inference_verified"] is False
    assert report["release_ready"] is False


def test_changed_runtime_is_rejected_before_execution(tmp_path: Path) -> None:
    runtime, models, output = candidate(tmp_path)
    (runtime / "exo.exe").write_bytes(b"changed binary")
    result = preflight(runtime, models, output)
    assert result.returncode != 0
    assert "Runtime executable hash mismatch" in result.stderr


def test_existing_output_is_preserved(tmp_path: Path) -> None:
    runtime, models, output = candidate(tmp_path)
    output.mkdir()
    sentinel = output / "evidence.txt"
    sentinel.write_text("existing evidence")
    result = preflight(runtime, models, output)
    assert result.returncode != 0
    assert "Output directory must be new" in result.stderr
    assert sentinel.read_text() == "existing evidence"


def test_model_directory_cannot_be_used_for_evidence(tmp_path: Path) -> None:
    runtime, models, _output = candidate(tmp_path)
    result = preflight(runtime, models, models / "evidence")
    assert result.returncode != 0
    assert "Output overlaps runtime or models" in result.stderr
    assert not (models / "evidence").exists()


def test_tampered_acceptance_helper_is_rejected_before_execution(
    tmp_path: Path,
) -> None:
    runtime, models, output = candidate(tmp_path)
    kit = tmp_path / "kit"
    kit.mkdir()
    hashes: dict[str, str] = {}
    for name in (
        SCRIPT.name,
        "check_inference.py",
        "validate_runtime.py",
        "consumer-acceptance.md",
    ):
        target = kit / name
        shutil.copyfile(SCRIPT.parent / name, target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (kit / "kit-manifest.json").write_text(
        json.dumps({"schema": 1, "file_sha256": hashes})
    )
    (kit / "validate_runtime.py").write_text(
        "raise SystemExit('tampered helper must never run')"
    )
    shell = shutil.which("pwsh")
    assert shell is not None
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-File",
            str(kit / SCRIPT.name),
            "-RuntimeDirectory",
            str(runtime),
            "-ModelDirectory",
            str(models),
            "-OutputDirectory",
            str(output),
            "-AllowDeveloperMachine",
            "-PreflightOnly",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode != 0
    assert "Acceptance kit hash mismatch" in result.stderr
    assert not output.exists()


def test_inventory_distinguishes_store_shortcuts_and_real_developer_software() -> None:
    shell = shutil.which("pwsh")
    assert shell is not None
    # Load only the inventory classifiers through the PowerShell AST; never run a candidate.
    source = str(SCRIPT).replace("'", "''")
    code = """
    $tokens=$null; $errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile('SOURCE',[ref]$tokens,[ref]$errors)
    foreach ($name in @('Test-AppInstallerAlias','Test-DeveloperSoftwareName')) {
        $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$false)
        if (-not $function) { throw "Missing inventory classifier $name" }
        . ([ScriptBlock]::Create($function.Extent.Text))
    }
    $alias=Join-Path $env:LOCALAPPDATA 'Microsoft/WindowsApps/python.exe'
    $identity=[Text.Encoding]::Unicode.GetBytes("Microsoft.DesktopAppInstaller_8wekyb3d8bbwe`0")
    $dump="Reparse Tag Value : 0x8000001b`n"
    for ($offset=0; $offset -lt $identity.Length; $offset+=16) {
        $end=[Math]::Min($offset+15,$identity.Length-1)
        $hex=($identity[$offset..$end] | ForEach-Object { $_.ToString('x2') }) -join ' '
        $dump+=('{0:x4}:  {1}  ........' -f $offset,$hex)+"`n"
    }
    @(
        (Test-AppInstallerAlias $alias "0x8000001b`nMicrosoft.DesktopAppInstaller_8wekyb3d8bbwe"),
        (Test-AppInstallerAlias $alias $dump),
        (Test-AppInstallerAlias $alias "0x8000001b`nPythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0"),
        (Test-AppInstallerAlias 'C:/Python313/python.exe' "0x8000001b`nMicrosoft.DesktopAppInstaller_8wekyb3d8bbwe"),
        (Test-DeveloperSoftwareName 'Intel(R) Trusted Connect Service Client x86'),
        (Test-DeveloperSoftwareName 'Microsoft Visual Studio Code (User)'),
        (Test-DeveloperSoftwareName 'Microsoft Visual Studio Build Tools 2022'),
        (Test-DeveloperSoftwareName 'Python 3.13.9 (64-bit)'),
        (Test-DeveloperSoftwareName 'Rustup')
    ) | ConvertTo-Json -Compress
    """.replace("SOURCE", source)
    result = subprocess.run(
        [shell, "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        True,
        True,
        False,
        False,
        False,
        False,
        True,
        True,
        True,
    ]
