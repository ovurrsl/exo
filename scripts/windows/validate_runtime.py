"""Reject package drift before and after installer staging; never run the node."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def validate_runtime(runtime: Path) -> int:
    if runtime.is_symlink() or runtime.is_junction():
        raise ValueError("Runtime root cannot be a link or junction")
    manifest_path = runtime / "runtime-manifest.json"
    if manifest_path.is_symlink() or manifest_path.is_junction():
        raise ValueError("Runtime manifest cannot be a link or junction")
    manifest = cast(
        dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    if manifest.get("schema") != 2:
        raise ValueError("A schema 2 manifest with all runtime file hashes is required")
    hashes_value = manifest.get("file_sha256")
    if not isinstance(hashes_value, dict) or not hashes_value:
        raise ValueError("Runtime file hashes are missing")
    hashes = cast(dict[str, object], hashes_value)
    for name, expected in hashes.items():
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or ":" in name
            or path.is_absolute()
            or PureWindowsPath(name).drive
            or ".." in path.parts
            or path.as_posix() != name
            or name == "runtime-manifest.json"
        ):
            raise ValueError(f"invalid manifest path: {name}")
        if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
            raise ValueError(f"Invalid runtime hash: {name}")
    actual: dict[str, Path] = {}
    for path in runtime.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Runtime links and junctions are forbidden: {path}")
        if path.is_file() and path != manifest_path:
            actual[path.relative_to(runtime).as_posix()] = path
    if actual.keys() != hashes.keys():
        changed = sorted(actual.keys() ^ hashes.keys())
        raise ValueError("Runtime file set differs: " + ", ".join(changed))
    for name, path in actual.items():
        if digest(path) != hashes[name]:
            raise ValueError("Runtime hash mismatch: " + name)
    binaries = {
        name: hashes[name]
        for name in hashes
        if PurePosixPath(name).suffix.lower() in {".dll", ".pyd", ".exe"}
    }
    if manifest.get("binary_sha256") != binaries or "exo.exe" not in binaries:
        raise ValueError("Native binary hashes disagree with complete runtime hashes")
    gates_value = manifest.get("runtime_gates")
    if not isinstance(gates_value, dict):
        raise ValueError("Runtime acceptance gates are missing")
    gates = cast(dict[str, object], gates_value)
    if (
        gates.get("passed") is not True
        or gates.get("frozen") is not True
        or gates.get("device") != "gpu"
    ):
        raise ValueError("A passing frozen GPU gate is required")
    results = gates.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("Individual runtime gates are missing")
    for result in cast(list[object], results):
        if not isinstance(result, dict):
            raise ValueError("Invalid individual runtime gate")
        check = cast(dict[str, object], result)
        if check.get("pass") is not True or check.get("exit_code") != check.get(
            "expected"
        ):
            raise ValueError("An individual runtime gate failed")
    return len(actual)


class Arguments(argparse.Namespace):
    runtime: Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    args = Arguments()
    parser.parse_args(namespace=args)
    try:
        count = validate_runtime(args.runtime)
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
    print(f"Validated {count} frozen runtime files")


if __name__ == "__main__":
    main()
