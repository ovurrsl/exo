"""Executable release gates, usable from Python and the frozen Exo runtime.

Loopback gates check the ring implementation, not Mac/Windows interoperability.
The latter needs a real Mac and is a separate release requirement.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import importlib.metadata
import json
import multiprocessing
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--runtime-check"]
    return [sys.executable, str(Path(__file__).resolve())]


def _kill_process_tree(pid: int) -> None:
    import psutil

    try:
        parent = psutil.Process(pid)
        owned = [*reversed(parent.children(recursive=True)), parent]
    except psutil.NoSuchProcess:
        return
    for process in owned:
        with contextlib.suppress(psutil.NoSuchProcess):
            process.kill()
    psutil.wait_procs(owned, timeout=5)


def _spawn_child(queue: multiprocessing.queues.Queue) -> None:
    import exo

    queue.put((exo.__version__, os.getpid()))


def _captured_child() -> None:
    os.write(1, b"frozen-stdout\n")
    os.write(2, b"frozen-stderr\n")
    raise SystemExit(7)


async def _async_spawn_check() -> None:
    from anyio import EndOfStream, create_task_group, fail_after

    from exo.utils.async_process import AsyncProcess
    from exo.utils.channels import Receiver

    stdout, stderr = bytearray(), bytearray()
    process = AsyncProcess(target=_captured_child)

    async def collect(stream: Receiver[bytes], output: bytearray) -> None:
        while True:
            try:
                output.extend(await stream.receive())
            except EndOfStream:
                return

    with fail_after(30):
        async with create_task_group() as group:
            await group.start(process.run)
            group.start_soon(collect, process.stdout, stdout)
            group.start_soon(collect, process.stderr, stderr)
            assert await process.wait() == 7
    assert bytes(stdout) == b"frozen-stdout\n"
    assert bytes(stderr) == b"frozen-stderr\n"


def _sparse_large_file(path: Path) -> None:
    # A valid contiguous tensor layout; only the final four values are evaluated.
    # This checks real seeks/reads beyond 2 GiB without allocating a 2 GiB tensor.
    padding = 1024 * 2097153
    header = json.dumps(
        {
            "padding": {
                "dtype": "U8",
                "shape": [1024, 2097153],
                "data_offsets": [0, padding],
            },
            "tail": {
                "dtype": "F32",
                "shape": [4],
                "data_offsets": [padding, padding + 16],
            },
        },
        separators=(",", ":"),
    ).encode("ascii")
    header += b" " * ((-len(header)) % 8)
    with path.open("wb") as stream:
        if sys.platform == "win32":
            import msvcrt

            returned = ctypes.c_ulong()
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            control = kernel32.DeviceIoControl
            control.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.c_void_p,
            ]
            control.restype = ctypes.c_int
            if not control(
                msvcrt.get_osfhandle(stream.fileno()),
                0x900C4,
                None,
                0,
                None,
                0,
                ctypes.byref(returned),
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        stream.write(struct.pack("<Q", len(header)))
        stream.write(header)
        stream.seek(8 + len(header) + padding)
        stream.write(struct.pack("<4f", 1.25, -2.5, 3.75, 4.0))
    if path.stat().st_size <= 2**31:
        raise AssertionError("large-file gate did not create a >2 GiB file")


def _worker(args: argparse.Namespace) -> int:
    if args.worker == "async-spawn":
        import anyio

        anyio.run(_async_spawn_check)
        print("captured async spawn passed", flush=True)
        return 0
    if args.worker == "spawn":
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        child = context.Process(target=_spawn_child, args=(queue,))
        child.start()
        try:
            version, pid = queue.get(timeout=30)
            child.join(30)
            if child.is_alive() or child.exitcode != 0 or pid == os.getpid():
                raise AssertionError("frozen spawn failed")
            print("spawn", version, pid, flush=True)
        finally:
            if child.is_alive():
                assert child.pid is not None
                _kill_process_tree(child.pid)
            child.join()
            queue.close()
        return 0
    if args.exo_hook:
        import exo  # installs the Windows MLX stream shutdown hook

        assert exo.__version__

    import mlx.core as mx

    mx.set_default_device(mx.gpu if args.device == "gpu" else mx.cpu)
    if args.worker == "info":
        print(
            json.dumps(
                {
                    "mlx": importlib.metadata.version("mlx"),
                    "module": mx.__file__,
                    "device": str(mx.default_device()),
                    "ring": mx.distributed.is_available("ring"),
                    "frozen": bool(getattr(sys, "frozen", False)),
                    "native_binary_sha256": {
                        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in Path(mx.__file__).parent.iterdir()
                        if path.is_file() and path.suffix.lower() in {".dll", ".pyd"}
                    },
                }
            ),
            flush=True,
        )
        if args.ring_sizes and not mx.distributed.is_available("ring"):
            raise AssertionError("MLX ring is missing")
        return 0
    if args.worker == "import":
        return 7
    if args.worker == "unicode-io":
        folder = Path.cwd() / "Türkçe 模型 🙂"
        folder.mkdir(parents=True, exist_ok=True)
        with mx.stream(mx.cpu):
            tensors = {
                "fp32": mx.array([[1.25, -2.5], [3.75, 4.0]], dtype=mx.float32),
                "fp16": mx.array([[1.25, -2.5], [3.75, 4.0]], dtype=mx.float16),
                "bf16": mx.array([[1.25, -2.5], [3.75, 4.0]], dtype=mx.bfloat16),
                "int32": mx.array([[1, 2], [3, 4]], dtype=mx.int32),
            }
            for path in (
                Path.cwd() / "ascii.safetensors",
                folder / "ağırlık 权重.safetensors",
            ):
                mx.save_safetensors(str(path), tensors)
                loaded = mx.load(str(path))
                for name, expected in tensors.items():
                    assert loaded[name].dtype == expected.dtype
                    assert loaded[name].tolist() == expected.tolist()
            try:
                mx.load(str(folder / "missing.safetensors"))
            except RuntimeError:
                pass
            else:
                raise AssertionError("Missing Unicode model file was accepted")
            try:
                mx.load("invalid-\udcff.safetensors")
            except (UnicodeError, ValueError, TypeError):
                pass
            except RuntimeError as error:
                # Nanobind rejects unpaired surrogates before calling C++ IO.
                # Accept this specific conversion rejection, not arbitrary IO errors.
                if str(error) != "bad cast":
                    raise
            else:
                raise AssertionError("Malformed UTF8 model path was accepted")
        print(
            json.dumps(
                {
                    "unicode_io_passed": True,
                    "folder": str(folder),
                    "ascii_and_unicode": True,
                }
            ),
            flush=True,
        )
        return 7
    if args.worker in {"compute", "compile"}:
        if args.worker == "compute":
            array = mx.ones((1024, 1024))
            result = (array @ array).sum()
            mx.eval(result)
            assert result.item() == 1024**3
        else:
            # CPU fusion must remain callable without cl.exe. GPU must still fuse
            # through bundled NVRTC, including a fresh cache and strided input.
            compiled = mx.compile(lambda value: mx.sin(value) + value * 2)
            value = mx.arange(2048, dtype=mx.float32)[::2] / 100
            expected = mx.sin(value) + value * 2
            actual = compiled(value)
            mx.eval(actual, expected)
            assert mx.allclose(actual, expected, atol=1e-5).item()
            if args.device == "gpu":
                # A GPU-default graph can contain CPU-stream primitives. The
                # default-device availability check alone does not protect them.
                def mixed_stream(input_value: mx.array) -> mx.array:
                    cpu_value = mx.add(
                        mx.sin(input_value, stream=mx.cpu),
                        mx.multiply(input_value, 2, stream=mx.cpu),
                        stream=mx.cpu,
                    )
                    return mx.add(cpu_value, input_value, stream=mx.gpu)

                mixed_result = mx.compile(mixed_stream)(value)
                mx.eval(mixed_result)
                assert mx.allclose(mixed_result, expected + value, atol=1e-5).item()
        print(args.worker, args.device, "passed", flush=True)
        if args.worker == "compile" and sys.platform == "win32":
            cpu_jit = Path(os.environ["TEMP"]) / "mlx"
            if cpu_jit.exists() and any(cpu_jit.rglob("*.dll")):
                raise AssertionError(
                    "CPU JIT emitted a DLL; a consumer would need MSVC"
                )
        return 7
    if args.worker == "large":
        path = Path(args.large_file)
        if path.stat().st_size <= 2**31:
            raise AssertionError("LargeFile must be larger than 2 GiB")
        arrays = mx.load(str(path))
        if args.generated_large:
            mx.eval(arrays["tail"])
            assert arrays["tail"].tolist() == [1.25, -2.5, 3.75, 4.0]
        else:
            mx.eval(list(arrays.values()))
        print(
            "loaded", path.stat().st_size, "bytes", len(arrays), "tensors", flush=True
        )
        return 7
    if args.worker == "ring-missing":
        try:
            mx.distributed.init(strict=True, backend="ring")
        except RuntimeError as error:
            print("missing peer rejected:", error, flush=True)
            return 23
        raise AssertionError("missing peer was accepted")
    group = mx.distributed.init(strict=True, backend="ring")
    rank, size = group.rank(), group.size()
    if args.worker in {"ring-loss", "ring-stall"}:
        mx.eval(mx.sum(mx.ones((4096,))))
        Path(args.marker + f".{rank}").touch()
        if rank == 1:
            time.sleep(args.timeout * 2)
            return 0
        # Give the parent time to kill a connected peer or let a live peer stall.
        time.sleep(1)
        try:
            mx.eval(mx.distributed.all_sum(mx.ones((4096,)), group=group))
        except RuntimeError as error:
            print("failed peer rejected:", error, flush=True)
            return 23
        raise AssertionError("failed/stalled peer was accepted")
    for dtype in (mx.float32, mx.float16, mx.bfloat16, mx.int32):
        for length in (4096, 2097153):
            backing = (mx.arange(length * 2, dtype=mx.int32) % 13).astype(dtype)
            base = backing[::2]
            value = (backing + rank + 1)[::2]
            sum_value = mx.distributed.all_sum(value, group=group)
            max_value = mx.distributed.all_max(value, group=group)
            min_value = mx.distributed.all_min(value, group=group)
            gather_value = mx.distributed.all_gather(value, group=group)
            mx.eval(sum_value, max_value, min_value, gather_value)
            assert mx.array_equal(
                sum_value, base * size + size * (size + 1) // 2
            ).item()
            assert mx.array_equal(max_value, base + size).item()
            assert mx.array_equal(min_value, base + 1).item()
            assert mx.array_equal(
                gather_value, mx.concatenate([base + r + 1 for r in range(size)])
            ).item()
            print("ring", rank, size, dtype, length, "collectives passed", flush=True)
            mx.clear_cache()
        payload = mx.arange(8192, dtype=mx.int32).astype(dtype)[::2]
        if rank == 0:
            mx.eval(mx.distributed.send(payload, 1, group=group))
        elif rank == 1:
            received = mx.distributed.recv(payload.shape, dtype, 0, group=group)
            mx.eval(received)
            assert mx.array_equal(received, payload).item()
        mx.eval(mx.distributed.all_sum(mx.array(1), group=group))
    try:
        group.split(rank % 2)
    except RuntimeError as error:
        if "not supported" not in str(error):
            raise
    else:
        raise AssertionError("ring split contract unexpectedly changed")
    print("rank", rank, "ring complete", flush=True)
    return 7


def _hosts(work: Path, size: int, tag: str) -> Path:
    sockets = [socket.socket() for _ in range(size)]
    try:
        for listener in sockets:
            listener.bind(("127.0.0.1", 0))
        hosts = [[f"127.0.0.1:{listener.getsockname()[1]}"] for listener in sockets]
    finally:
        for listener in sockets:
            listener.close()
    directory = work / "Türkçe 模型 🙂"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"hosts-群-{tag}.json"
    path.write_text(json.dumps(hosts), encoding="ascii")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "gpu"), default="gpu")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--ring-sizes", type=int, nargs="*", default=[2, 3, 4])
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--large-file")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--worker",
        choices=(
            "info",
            "import",
            "compute",
            "compile",
            "unicode-io",
            "large",
            "spawn",
            "async-spawn",
            "ring",
            "ring-missing",
            "ring-loss",
            "ring-stall",
        ),
    )
    parser.add_argument("--exo-hook", action="store_true")
    parser.add_argument("--generated-large", action="store_true")
    parser.add_argument("--marker", default="")
    args = parser.parse_args(argv)
    if args.worker:
        return _worker(args)
    if args.runs < 1 or args.timeout < 10 or any(size < 2 for size in args.ring_sizes):
        parser.error("runs >= 1, timeout >= 10, and ring sizes >= 2 are required")
    work = Path(tempfile.mkdtemp(prefix="exo-mlx-gate-"))
    results: list[dict[str, object]] = []
    environment = os.environ.copy()
    environment.pop("MLX_DISABLE_COMPILE", None)
    environment.pop("CUDA_PATH", None)
    environment.pop("CUDA_HOME", None)
    if sys.platform == "win32":
        # A clean consumer PATH: neither the CUDA Toolkit nor MSVC can rescue a
        # broken runtime bundle. NVIDIA's installed display driver is sufficient.
        environment["PATH"] = str(Path(os.environ["SYSTEMROOT"]) / "System32")
    environment["MLX_PTX_CACHE_DIR"] = str(work / "Türkçe 缓存 🙂" / "fresh-ptx-cache")
    fresh_temp = work / "fresh-temp"
    fresh_temp.mkdir()
    environment["TEMP"] = str(fresh_temp)
    environment["TMP"] = str(fresh_temp)

    def start(
        worker: str,
        tag: str,
        extra: list[str] | None = None,
        updates: dict[str, str] | None = None,
    ) -> tuple[subprocess.Popen[bytes], Path, float]:
        output = work / f"{tag}.log"
        child_environment = environment | (updates or {})
        command = (
            _command()
            + [
                "--worker",
                worker,
                "--device",
                args.device,
                "--timeout",
                str(args.timeout),
            ]
            + (extra or [])
        )
        with output.open("wb") as log:
            child = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=child_environment,
                cwd=work,
            )
        return child, output, time.monotonic()

    def finish(
        task: tuple[subprocess.Popen[bytes], Path, float], tag: str, expected: int
    ) -> None:
        child, output, started = task
        try:
            code = child.wait(
                timeout=max(1, args.timeout - (time.monotonic() - started))
            )
            passed = code == expected
        except subprocess.TimeoutExpired:
            _kill_process_tree(child.pid)
            child.wait()
            code, passed = None, False
        record = {
            "check": tag,
            "pass": passed,
            "exit_code": code,
            "expected": expected,
            "seconds": round(time.monotonic() - started, 3),
            "log": str(output),
        }
        results.append(record)
        print(json.dumps(record), flush=True)
        if not passed:
            print(output.read_text(errors="replace")[-4000:], flush=True)

    finish(
        start("info", "info", ["--ring-sizes", *map(str, args.ring_sizes)]), "info", 0
    )
    finish(start("spawn", "spawn"), "spawn", 0)
    finish(start("async-spawn", "async-spawn"), "async-spawn", 0)
    finish(start("unicode-io", "unicode-io", ["--exo-hook"]), "unicode-io", 7)
    for run in range(args.runs):
        for worker in ("import", "compute"):
            for hook in (False, True):
                tag = f"{worker}-{'exo' if hook else 'bare'}-{run}"
                finish(start(worker, tag, ["--exo-hook"] if hook else []), tag, 7)
    for device in ("cpu", "gpu") if args.device == "gpu" else ("cpu",):
        tag = f"compilerless-{device}"
        finish(start("compile", tag, ["--device", device, "--exo-hook"]), tag, 7)
    large = Path(args.large_file) if args.large_file else work / "over-2gib.safetensors"
    if not args.large_file:
        _sparse_large_file(large)
    finish(
        start(
            "large",
            "large-file",
            ["--large-file", str(large), "--exo-hook"]
            + (["--generated-large"] if not args.large_file else []),
        ),
        "large-file",
        7,
    )
    for size in args.ring_sizes:
        hosts = _hosts(work, size, str(size))
        tasks = [
            start(
                "ring",
                f"ring-{size}-{rank}",
                ["--exo-hook"],
                {"MLX_HOSTFILE": str(hosts), "MLX_RANK": str(rank)},
            )
            for rank in range(size)
        ]
        for rank, task in enumerate(tasks):
            finish(task, f"ring-{size}-{rank}", 7)
    if args.ring_sizes:
        hosts = _hosts(work, 2, "missing")
        finish(
            start(
                "ring-missing",
                "missing-peer",
                ["--exo-hook"],
                {
                    "MLX_HOSTFILE": str(hosts),
                    "MLX_RANK": "0",
                    "MLX_RING_IO_TIMEOUT_SECONDS": "5",
                },
            ),
            "missing-peer",
            23,
        )
        for mode in ("ring-loss", "ring-stall"):
            hosts = _hosts(work, 2, mode)
            marker = work / mode
            tasks = [
                start(
                    mode,
                    f"{mode}-{rank}",
                    ["--exo-hook", "--marker", str(marker)],
                    {
                        "MLX_HOSTFILE": str(hosts),
                        "MLX_RANK": str(rank),
                        "MLX_RING_IO_TIMEOUT_SECONDS": "10"
                        if mode == "ring-stall"
                        else "5",
                    },
                )
                for rank in range(2)
            ]
            deadline = time.monotonic() + min(30, args.timeout)
            while time.monotonic() < deadline and not all(
                Path(str(marker) + f".{r}").exists() for r in range(2)
            ):
                if any(task[0].poll() is not None for task in tasks):
                    break
                time.sleep(0.05)
            if mode == "ring-loss":
                _kill_process_tree(tasks[1][0].pid)
            elif tasks[0][0].poll() is None:
                import psutil

                time.sleep(1.5)
                monitored = psutil.Process(tasks[0][0].pid)
                before = {
                    process.pid: process.cpu_times()
                    for process in (monitored, *monitored.children(recursive=True))
                }
                sampled_at = time.monotonic()
                time.sleep(2)
                after = {
                    process.pid: process.cpu_times()
                    for process in (monitored, *monitored.children(recursive=True))
                }
                cpu_percent = (
                    sum(
                        times.user
                        + times.system
                        - before[pid].user
                        - before[pid].system
                        for pid, times in after.items()
                        if pid in before
                    )
                    / (time.monotonic() - sampled_at)
                    * 100
                )
                record = {
                    "check": "stalled-peer-idle-cpu",
                    "pass": cpu_percent < 25,
                    "cpu_percent_of_one_core": round(cpu_percent, 2),
                }
                results.append(record)
                print(json.dumps(record), flush=True)
            finish(tasks[0], mode, 23)
            if tasks[1][0].poll() is None:
                _kill_process_tree(tasks[1][0].pid)
            tasks[1][0].wait()
    report = {
        "passed": all(record["pass"] for record in results),
        "device": args.device,
        "frozen": bool(getattr(sys, "frozen", False)),
        "work_dir": str(work),
        "results": results,
        "mac_windows_interoperability": "requires physical Mac release gate",
        "native_identity": next(
            (
                json.loads(line)
                for line in (work / "info.log").read_text(errors="replace").splitlines()
                if line.startswith('{"mlx":')
            ),
            None,
        ),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    # Remove our generated sparse fixture; keep small diagnostics for failed runs.
    if not args.large_file:
        large.unlink(missing_ok=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
