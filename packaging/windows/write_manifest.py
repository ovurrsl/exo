"""Record the exact native runtime inputs and packaged binary hashes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PINNED_MLX = "64ea011cb65f14d9ce2737e60db9a4ae91ed7441"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--gates", type=Path, required=True)
    parser.add_argument("--source-inputs", type=Path, required=True)
    args = parser.parse_args()
    provenance_path = Path(str(args.wheel) + ".provenance.json")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8-sig"))
    patch = args.root / "scripts/windows/mlx/mlx-windows-ring-v0.32.3.patch"
    if provenance["upstream_commit"] != PINNED_MLX:
        raise SystemExit("Wheel was built from a different MLX upstream commit")
    if provenance["patch_sha256"] != sha256(patch):
        raise SystemExit("Wheel provenance does not match the checked-in MLX patch")
    if provenance["wheel_sha256"] != sha256(args.wheel):
        raise SystemExit("Wheel hash does not match its build provenance")
    with zipfile.ZipFile(args.wheel) as wheel:
        for name in wheel.namelist():
            if name.startswith("mlx/") and Path(name).suffix.lower() in {
                ".dll",
                ".pyd",
            }:
                packaged = args.runtime / "_internal" / name
                if not packaged.is_file():
                    raise SystemExit(
                        f"Wheel native file missing from frozen runtime: {name}"
                    )
                expected = hashlib.sha256(wheel.read(name)).hexdigest()
                if sha256(packaged) != expected:
                    raise SystemExit(
                        f"Packaged MLX binary differs from reviewed wheel: {name}"
                    )
    gates = json.loads(args.gates.read_text(encoding="utf-8"))
    if not gates["passed"] or not gates["frozen"] or gates["device"] != "gpu":
        raise SystemExit("A passing frozen CUDA runtime gate is required")
    if any(
        not check["pass"] or check.get("exit_code") != check.get("expected")
        for check in gates["results"]
    ):
        raise SystemExit("An individual frozen CUDA runtime gate failed")
    with zipfile.ZipFile(args.wheel) as wheel:
        for name in wheel.namelist():
            if name.startswith("mlx/") and Path(name).suffix.lower() in {
                ".dll",
                ".pyd",
            }:
                expected = hashlib.sha256(wheel.read(name)).hexdigest()
                observed = gates["native_identity"]["native_binary_sha256"].get(
                    Path(name).name
                )
                if observed != expected:
                    raise SystemExit(
                        "Frozen gate exercised a different MLX binary: " + name
                    )
    required_checks = {
        "info",
        "spawn",
        "async-spawn",
        "unicode-io",
        "compilerless-cpu",
        "compilerless-gpu",
        "large-file",
        "missing-peer",
        "ring-loss",
        "stalled-peer-idle-cpu",
        "ring-stall",
    }
    required_checks.update(
        f"ring-{size}-{rank}" for size in (2, 3, 4) for rank in range(size)
    )
    required_checks.update(
        f"{operation}-{hook}-{run}"
        for operation in ("import", "compute")
        for hook in ("bare", "exo")
        for run in range(3)
    )
    if not required_checks.issubset({check["check"] for check in gates["results"]}):
        raise SystemExit("Frozen CUDA gate is missing mandatory checks")
    source_commit = subprocess.check_output(
        ["git", "-C", str(args.root), "rev-parse", "HEAD"], text=True
    ).strip()
    source_diff = subprocess.check_output(
        ["git", "-C", str(args.root), "diff", "--binary", "HEAD"]
    )
    files = {
        str(path.relative_to(args.runtime)).replace("\\", "/"): sha256(path)
        for path in sorted(args.runtime.rglob("*"))
        if path.is_file() and path.name != "runtime-manifest.json"
    }
    binaries = {
        name: value
        for name, value in files.items()
        if Path(name).suffix.lower() in {".dll", ".pyd", ".exe"}
    }
    manifest = {
        "schema": 2,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "exo_commit": source_commit,
        "tracked_working_diff_sha256": hashlib.sha256(source_diff).hexdigest(),
        "runtime_input_sha256": json.loads(
            args.source_inputs.read_text(encoding="utf-8")
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "mlx": provenance,
        "packages": {
            dist.metadata["Name"]: dist.version
            for dist in importlib.metadata.distributions()
        },
        "binary_sha256": binaries,
        "file_sha256": files,
        "runtime_gates": gates,
        "physical_mac_windows_cluster_gate": "pending",
        "release_ready": False,
    }
    (args.runtime / "runtime-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
