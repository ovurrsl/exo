"""Hash runtime source inputs and reject edits made during a package build."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def runtime_inputs(root: Path) -> dict[str, str]:
    files = {
        root / "pyproject.toml",
        root / "uv.lock",
        root / "scripts/windows/mlx/check_mlx.py",
        root / "scripts/windows/check_inference.py",
        root / "scripts/windows/check_image_inference.py",
        root / "scripts/windows/mlx/mlx-windows-ring-v0.32.3.patch",
    }
    for directory in ("src/exo", "resources", "dashboard/build", "packaging/windows"):
        for path in (root / directory).rglob("*"):
            if path.is_file() and not set(path.parts).intersection(
                {"__pycache__", "wheels"}
            ):
                files.add(path)
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(files)
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = runtime_inputs(args.root)
    if args.check:
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        changed = sorted(
            name
            for name in previous.keys() | current.keys()
            if previous.get(name) != current.get(name)
        )
        if changed:
            raise SystemExit(
                "Runtime inputs changed during build: " + ", ".join(changed)
            )
    else:
        args.output.write_text(json.dumps(current, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
