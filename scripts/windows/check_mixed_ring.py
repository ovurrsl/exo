"""Run physical Metal/CUDA ring gates in both rank orders through authorized SSH.

Does not install packages, alter EXO.app, change firewall rules or promote a
release. A passing ring report does not establish distributed model inference.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import cast

MAC_BASELINE = "21a54c5ea0230a3bec1e1a786d200126c7e34ec6"
MAC_MLX = "0.32.0.dev20260506+cc3f3e60"
MAC_MLX_COMMIT = "cc3f3e60be1289506125f2fa19b73b05aa770df8"
MAC_MLX_URL = "https://github.com/rltakashige/mlx-jaccl-fix-small-recv.git"
ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "scripts/windows/mlx/check_mlx.py",
    "src/exo/worker/engines/mlx/cache.py",
    "src/exo/worker/engines/mlx/snapshot_guard.py",
    "src/exo/worker/engines/mlx/auto_parallel.py",
    "src/exo/worker/engines/mlx/builder.py",
)


def validate_peer(peer: dict[str, object], expected: dict[str, str]) -> None:
    if peer.get("commit") != MAC_BASELINE:
        raise ValueError("Mac commit differs from the approved baseline")
    if peer.get("sources") != expected:
        raise ValueError("Mac/Windows protocol source mismatch")
    version = peer.get("mlx")
    if (
        peer.get("system") != "Darwin"
        or peer.get("machine") != "arm64"
        or not isinstance(version, str)
        or re.fullmatch(r"0\.32\.0\.dev[0-9]{8}\+cc3f3e60", version) is None
        or peer.get("ring") is not True
        or peer.get("gpu_value") != 16
    ):
        raise ValueError("Pinned Mac MLX/Metal kernel and ring are required")
    source = peer.get("mlx_source")
    if not isinstance(source, dict):
        raise ValueError("Pinned Mac MLX source provenance is required")
    source = cast(dict[str, object], source)
    vcs = source.get("vcs_info")
    if not isinstance(vcs, dict):
        raise ValueError("Pinned Mac MLX source provenance is required")
    vcs = cast(dict[str, object], vcs)
    if (
        source.get("url") != MAC_MLX_URL
        or vcs.get("vcs") != "git"
        or vcs.get("commit_id") != MAC_MLX_COMMIT
    ):
        raise ValueError("Mac MLX source differs from the pinned Git commit")


def rank_passed(exit_code: int, text: str, rank: int) -> bool:
    if exit_code != 7 or f"rank {rank} ring complete" not in text.splitlines():
        return False
    cases: set[tuple[str, int]] = set()
    for line in text.splitlines():
        match = re.fullmatch(
            rf"ring {rank} 2 (.+) (4096|2097153) collectives passed", line
        )
        if match:
            dtype = re.search(r"\b(float32|bfloat16|float16|int32)\b", match[1])
            if dtype:
                cases.add((dtype[1], int(match[2])))
    return cases == {
        (dtype, length)
        for dtype in ("float32", "float16", "bfloat16", "int32")
        for length in (4096, 2097153)
    }


# Only the isolated checkout's build directory is writable on the Mac.
REMOTE_COMMON = """
import contextlib, hashlib, importlib.metadata, json, os, platform
import signal, socket, subprocess, sys
from pathlib import Path
root = Path(config["checkout"]).resolve()
allowed = (Path.home() / "exo-windows-acceptance").resolve()
if not root.is_relative_to(allowed) or root.name != "21a54c5e-shared":
    raise ValueError("Mac checkout must be the isolated acceptance checkout")
os.environ["DEVELOPER_DIR"] = "/Applications/Xcode.app/Contents/Developer"
"""
REMOTE_PROBE = (
    REMOTE_COMMON
    + """
commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
sources = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in config["sources"]}
with socket.socket() as listener:
    listener.bind((config["mac_ip"], config["port"]))
import mlx.core as mx
mx.set_default_device(mx.gpu)
value = mx.sum(mx.ones((16,)))
mx.eval(value)
peer = dict(commit=commit, sources=sources, mlx=importlib.metadata.version("mlx"),
            mlx_source=json.loads(importlib.metadata.distribution("mlx").read_text("direct_url.json") or "null"),
            system=platform.system(), machine=platform.machine(),
            ring=mx.distributed.is_available("ring"), gpu_value=value.item())
print("EXO_MIXED_PROBE " + json.dumps(peer), flush=True)
"""
)
REMOTE_RANK = (
    REMOTE_COMMON
    + """
commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
sources = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in config["sources"]}
if commit != config["baseline"] or sources != config["expected"]:
    raise ValueError("Mac source changed after preflight")
if importlib.metadata.version("mlx") != config["mlx"]:
    raise ValueError("Mac MLX changed after preflight")
if json.loads(importlib.metadata.distribution("mlx").read_text("direct_url.json") or "null") != config["mlx_source"]:
    raise ValueError("Mac MLX source changed after preflight")
session = root / "build" / "physical-acceptance" / config["session"]
if session.is_symlink() or session.exists():
    raise ValueError("Remote acceptance session already exists")
if not session.parent.resolve().is_relative_to(root):
    raise ValueError("Remote acceptance parent escapes checkout")
session.mkdir(parents=True)
if not session.resolve().is_relative_to(root):
    raise ValueError("Remote acceptance session escapes checkout")
hostfile = session / "hosts.json"
hostfile.write_text(json.dumps(config["hosts"]), encoding="utf-8")
env = dict(os.environ, MLX_HOSTFILE=str(hostfile), MLX_RANK=str(config["rank"]),
           MLX_RING_TIMEOUT_MS="30000")
command = [str(root/".venv/bin/python"), str(root/"scripts/windows/mlx/check_mlx.py"),
           "--worker", "ring", "--device", "gpu", "--exo-hook"]
process = subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, start_new_session=True)
timed_out = False
try:
    output, _ = process.communicate(timeout=config["timeout"])
except subprocess.TimeoutExpired:
    timed_out = True
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    output, _ = process.communicate(timeout=5)
finally:
    if process.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
result = dict(exit_code=process.returncode, timed_out=timed_out,
              stdout=output.decode("utf-8", errors="replace"), session=str(session))
print("EXO_MIXED_RANK " + json.dumps(result), flush=True)
sys.exit(0 if process.returncode == 7 and not timed_out else 1)
"""
)


class Arguments(argparse.Namespace):
    ssh_target: str
    pc_ip: str
    ssh_key: Path
    known_hosts: Path
    ssh: str
    runtime: Path
    mac_checkout: str
    output: Path
    port: int
    timeout: int


def ssh_command(args: Arguments) -> list[str]:
    python = str(PurePosixPath(args.mac_checkout) / ".venv/bin/python")
    return [
        args.ssh,
        "-F",
        os.devnull,
        "-T",
        "-i",
        str(args.ssh_key.resolve()),
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "UpdateHostKeys=no",
        "-o",
        f"UserKnownHostsFile={args.known_hosts.resolve()}",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ForwardAgent=no",
        "-o",
        "ClearAllForwardings=yes",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        args.ssh_target,
        f"exec {shlex.quote(python)} -u -",
    ]


def remote_program(config: dict[str, object], body: str) -> bytes:
    return (
        "import json\nconfig = json.loads(" + repr(json.dumps(config)) + ")\n" + body
    ).encode("utf-8")


def read_record(text: str, marker: str) -> dict[str, object]:
    records = [
        line.removeprefix(marker)
        for line in text.splitlines()
        if line.startswith(marker)
    ]
    if len(records) != 1:
        raise ValueError("Remote result is missing or duplicated; inspect the SSH log")
    value = cast(object, json.loads(records[0]))
    if not isinstance(value, dict):
        raise ValueError("Remote result must be an object")
    return cast(dict[str, object], value)


def stop_owned(process: subprocess.Popen[bytes]) -> None:
    import psutil

    if process.poll() is not None:
        return
    with contextlib.suppress(psutil.NoSuchProcess):
        parent = psutil.Process(process.pid)
        children = list(reversed(parent.children(recursive=True)))
        for child in children:
            with contextlib.suppress(psutil.NoSuchProcess):
                child.kill()
        process.kill()
        _ = psutil.wait_procs(children, timeout=5)
    _ = process.wait(timeout=5)


def run_round(
    args: Arguments, config: dict[str, object], mac_rank: int
) -> dict[str, object]:
    hosts = [[f"{config['mac_ip']}:{args.port}"], [f"{args.pc_ip}:{args.port + 1}"]]
    if mac_rank == 1:
        hosts.reverse()
    config = {
        **config,
        "hosts": hosts,
        "rank": mac_rank,
        "timeout": args.timeout,
        "session": f"ring-{uuid.uuid4().hex}",
    }
    hostfile = args.output / f"hosts-mac-rank-{mac_rank}.json"
    hostfile.write_text(json.dumps(hosts), encoding="utf-8")
    remote_log = args.output / f"mac-rank-{mac_rank}.log"
    local_log = args.output / f"windows-rank-{1 - mac_rank}.log"
    processes: list[subprocess.Popen[bytes]] = []
    timed_out = False
    with remote_log.open("wb") as mac_output, local_log.open("wb") as pc_output:
        try:
            remote = subprocess.Popen(
                ssh_command(args),
                stdin=subprocess.PIPE,
                stdout=mac_output,
                stderr=subprocess.STDOUT,
            )
            processes.append(remote)
            assert remote.stdin is not None
            _ = remote.stdin.write(remote_program(config, REMOTE_RANK))
            remote.stdin.close()
            env = {
                **os.environ,
                "MLX_HOSTFILE": str(hostfile.resolve()),
                "MLX_RANK": str(1 - mac_rank),
                "MLX_RING_IO_TIMEOUT_SECONDS": "30",
            }
            local = subprocess.Popen(
                [
                    str(args.runtime / "exo.exe"),
                    "--runtime-check",
                    "--worker",
                    "ring",
                    "--device",
                    "gpu",
                    "--exo-hook",
                ],
                env=env,
                stdout=pc_output,
                stderr=subprocess.STDOUT,
            )
            processes.append(local)
            deadline = time.monotonic() + args.timeout + 20
            while any(process.poll() is None for process in processes):
                if time.monotonic() > deadline:
                    timed_out = True
                    break
                time.sleep(0.1)
        finally:
            for process in processes:
                stop_owned(process)
    if len(processes) != 2:
        raise RuntimeError("Both physical workers did not start")
    peer = read_record(
        remote_log.read_text(encoding="utf-8", errors="replace"), "EXO_MIXED_RANK "
    )
    remote_text = peer.get("stdout")
    remote_code = peer.get("exit_code")
    local_code = processes[1].returncode
    passed = (
        not timed_out
        and peer.get("timed_out") is False
        and processes[0].returncode == 0
        and isinstance(remote_code, int)
        and isinstance(remote_text, str)
        and local_code is not None
        and rank_passed(remote_code, remote_text, mac_rank)
        and rank_passed(
            local_code,
            local_log.read_text(encoding="utf-8", errors="replace"),
            1 - mac_rank,
        )
    )
    return {
        "mac_rank": mac_rank,
        "windows_rank": 1 - mac_rank,
        "hosts": hosts,
        "passed": passed,
        "timed_out": timed_out,
        "remote": peer,
        "windows_exit_code": local_code,
        "mac_log": str(remote_log),
        "windows_log": str(local_log),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-target", required=True)
    parser.add_argument("--pc-ip", required=True)
    parser.add_argument("--ssh-key", type=Path, required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--ssh", default=shutil.which("ssh") or "ssh")
    parser.add_argument("--runtime", type=Path, default=ROOT / "dist/windows/exo")
    parser.add_argument(
        "--mac-checkout",
        default="/Users/melisaovur/exo-windows-acceptance/21a54c5e-shared",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=59001)
    parser.add_argument("--timeout", type=int, default=120)
    args = Arguments()
    _ = parser.parse_args(namespace=args)
    match = re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*@([0-9.]+)", args.ssh_target)
    if not match:
        parser.error("SSH target must be user@IPv4 without shell metacharacters")
    mac_ip = str(ipaddress.IPv4Address(match[1]))
    _ = ipaddress.IPv4Address(args.pc_ip)
    checkout = PurePosixPath(args.mac_checkout)
    if (
        not checkout.is_absolute()
        or ".." in checkout.parts
        or checkout.name != "21a54c5e-shared"
    ):
        parser.error("Use the isolated absolute Mac acceptance checkout")
    if not 49152 <= args.port < 65535 or not 30 <= args.timeout <= 600:
        parser.error("Use two adjacent ring ports in 49152..65535 and timeout 30..600")
    if not args.ssh_key.is_file() or not args.known_hosts.is_file():
        parser.error(
            "Existing authorized SSH key and verified known-hosts are required"
        )
    if args.output.exists():
        parser.error(
            "Use a new acceptance output directory to preserve earlier evidence"
        )
    args.output.mkdir(parents=True)
    report: dict[str, object] = {
        "passed": False,
        "physical_ring_verified": False,
        "model_inference_verified": False,
        "phase": "preflight",
    }
    try:
        manifest = cast(
            dict[str, object],
            json.loads(
                (args.runtime / "runtime-manifest.json").read_text(encoding="utf-8")
            ),
        )
        hashes = cast(dict[str, str], manifest["runtime_input_sha256"])
        report["windows_runtime"] = {
            "manifest_sha256": hashlib.sha256(
                (args.runtime / "runtime-manifest.json").read_bytes()
            ).hexdigest(),
            "engine_sha256": hashlib.sha256(
                (args.runtime / "exo.exe").read_bytes()
            ).hexdigest(),
            "mlx": manifest["mlx"],
            "integrity_verified": False,
        }
        expected = {name: hashes[name] for name in SOURCES}
        for name, digest in expected.items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                raise ValueError(
                    f"Source differs from the frozen Windows candidate: {name}"
                )
        with socket.socket() as listener:
            listener.bind((args.pc_ip, args.port + 1))
        config: dict[str, object] = {
            "checkout": args.mac_checkout,
            "mac_ip": mac_ip,
            "port": args.port,
            "sources": list(SOURCES),
            "expected": expected,
            "baseline": MAC_BASELINE,
        }
        probe = subprocess.run(
            ssh_command(args),
            input=remote_program(config, REMOTE_PROBE),
            capture_output=True,
            timeout=45,
            check=False,
        )
        text = probe.stdout.decode("utf-8", errors="replace")
        (args.output / "mac-preflight.log").write_text(
            text + probe.stderr.decode("utf-8", errors="replace"), encoding="utf-8"
        )
        if probe.returncode != 0:
            raise RuntimeError(
                "Mac SSH/Metal preflight failed; inspect mac-preflight.log"
            )
        peer = read_record(text, "EXO_MIXED_PROBE ")
        validate_peer(peer, expected)
        config["mlx"] = peer["mlx"]
        config["mlx_source"] = peer["mlx_source"]
        report["mac"] = peer
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/windows/validate_runtime.py"),
                "--runtime",
                str(args.runtime),
            ],
            check=True,
        )
        cast(dict[str, object], report["windows_runtime"])["integrity_verified"] = True
        report["phase"] = "physical-ring"
        rounds = [run_round(args, config, rank) for rank in (0, 1)]
        report["rounds"] = rounds
        report["passed"] = all(item["passed"] is True for item in rounds)
        report["physical_ring_verified"] = report["passed"]
    except (
        ValueError,
        OSError,
        RuntimeError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        report["error"] = str(error)
    finally:
        (args.output / "mixed-ring.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] is True else 1)


if __name__ == "__main__":
    main()
