"""Target a stalled ring with CPU/GPU arrays and retain per-thread CPU evidence."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import psutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--checker", type=Path)
    parser.add_argument("--device", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="exo-stall-probe-"))
    sockets = [socket.socket() for _ in range(2)]
    for listener in sockets:
        listener.bind(("127.0.0.1", 0))
    hosts = [[f"127.0.0.1:{listener.getsockname()[1]}"] for listener in sockets]
    for listener in sockets:
        listener.close()
    hostfile = work / "hosts.json"
    hostfile.write_text(json.dumps(hosts), encoding="utf-8")
    command = [str(args.program.resolve())]
    command += [str(args.checker.resolve())] if args.checker else ["--runtime-check"]
    command += [
        "--worker",
        "ring-stall",
        "--device",
        args.device,
        "--exo-hook",
        "--marker",
        str(work / "ready"),
        "--timeout",
        "30",
    ]
    environment = os.environ.copy()
    environment["MLX_HOSTFILE"] = str(hostfile)
    environment["MLX_RING_IO_TIMEOUT_SECONDS"] = "8"
    for key in ("CUDA_PATH", "CUDA_HOME", "MLX_DISABLE_COMPILE"):
        environment.pop(key, None)
    environment["PATH"] = str(Path(environment["SYSTEMROOT"]) / "System32")
    processes: list[subprocess.Popen[bytes]] = []
    logs = []
    try:
        for rank in range(2):
            log = (work / f"rank-{rank}.log").open("wb")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    command,
                    env=environment | {"MLX_RANK": str(rank)},
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            )
        deadline = time.monotonic() + 30
        while not all((work / f"ready.{rank}").exists() for rank in range(2)):
            if time.monotonic() > deadline or any(
                p.poll() is not None for p in processes
            ):
                raise RuntimeError(
                    f"Ring workers failed before readiness; inspect {work}"
                )
            time.sleep(0.1)
        time.sleep(1.7)
        process = psutil.Process(processes[0].pid)
        before = {
            (p.pid, t.id): t.user_time + t.system_time
            for p in (process, *process.children(recursive=True))
            for t in p.threads()
        }
        start = time.monotonic()
        time.sleep(2)
        duration = time.monotonic() - start
        threads = {
            f"{p.pid}/{t.id}": round(
                100 * (t.user_time + t.system_time - before[(p.pid, t.id)]) / duration,
                2,
            )
            for p in (process, *process.children(recursive=True))
            for t in p.threads()
            if (p.pid, t.id) in before
            and t.user_time + t.system_time > before[(p.pid, t.id)]
        }
        exit_code = processes[0].wait(timeout=20)
        result = {
            "device": args.device,
            "program": str(args.program),
            "work": str(work),
            "threads_percent_of_one_cpu": threads,
            "total_percent_of_one_cpu": round(sum(threads.values()), 2),
            "exit_code": exit_code,
            "expected_exit_code": 23,
        }
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
        if exit_code != 23:
            raise SystemExit(
                "Stalled worker did not report the expected bounded exception"
            )
    finally:
        for process in processes:
            if process.poll() is None:
                parent = psutil.Process(process.pid)
                owned = [*reversed(parent.children(recursive=True)), parent]
                for descendant in owned:
                    with contextlib.suppress(psutil.NoSuchProcess):
                        descendant.kill()
                psutil.wait_procs(owned, timeout=5)
            process.wait()
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
