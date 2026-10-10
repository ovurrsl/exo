"""Bounded two-rank CUDA/CPU cache capability, eviction and divergence gate."""

import json
import os
import socket
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from scripts.windows.mlx.check_mlx import _kill_process_tree


def worker(rank: int, hostfile: str, stage: str) -> None:
    os.environ["MLX_RANK"] = str(rank)
    os.environ["MLX_HOSTFILE"] = hostfile
    from exo.utils.rlimits import install_windows_resource_shim

    install_windows_resource_shim()
    import mlx.core as mx

    from exo.worker.engines.mlx import cache

    # A real CPU rank and CUDA rank exercise device flags and CPU collectives
    # on this host. Physical Mac/Windows clustering needs its separate gate.
    mx.set_default_device(mx.gpu if rank == 0 else mx.cpu)
    group = mx.distributed.init(strict=True, backend="ring")
    assert cache.discover_cuda_cache_group(group), "The CUDA peer was not discovered"
    prefix = cache.KVPrefixCache(group, cuda_group=True)
    with mock.patch.object(cache, "get_memory_used_percentage", return_value=0.0):
        if stage == "identity":
            try:
                prefix.add_kv_cache(mx.array([rank + 1], dtype=mx.int32), [])
            except RuntimeError as error:
                assert "diverged" in str(error)
                print(f"rank {rank}: prompt identity rejected collectively", flush=True)
            else:
                raise AssertionError("A mismatched prompt identity was accepted")
        else:
            prefix.add_kv_cache(mx.array([1, 2, 3], dtype=mx.int32), [])
            if stage == "empty":
                if rank == 0:
                    prefix.clear()
                try:
                    prefix._evict_if_needed()
                except RuntimeError as error:
                    assert "diverged" in str(error)
                    print(
                        f"rank {rank}: empty divergence rejected collectively",
                        flush=True,
                    )
                else:
                    raise AssertionError(
                        "An empty/nonempty cache divergence was accepted"
                    )
            elif stage == "pressure":
                with mock.patch.object(
                    cache, "get_memory_used_percentage", return_value=float(rank == 1)
                ):
                    prefix._evict_if_needed()
                assert not prefix.caches and not prefix.prompts
                print(f"rank {rank}: peer pressure evicted the same entry", flush=True)
            else:
                raise ValueError(f"Unexpected stage: {stage}")
    sys.exit(7)


def main() -> None:
    print(f"CUDA/CPU cache gate using MLX {version('mlx')}", flush=True)
    for stage in ("pressure", "identity", "empty"):
        children: list[subprocess.Popen[str]] = []
        with TemporaryDirectory(prefix="exo-cache-gate-", dir=Path.cwd()) as temporary:
            with socket.socket() as first, socket.socket() as second:
                first.bind(("127.0.0.1", 0))
                second.bind(("127.0.0.1", 0))
                hosts = [
                    [f"127.0.0.1:{first.getsockname()[1]}"],
                    [f"127.0.0.1:{second.getsockname()[1]}"],
                ]
                hostfile = Path(temporary) / "hosts.json"
                hostfile.write_text(json.dumps(hosts), encoding="utf-8")
            deadline = time.monotonic() + 20
            try:
                for rank in range(2):
                    code = (
                        "from scripts.windows.tests.check_cache_acceptance import worker; "
                        f"worker({rank}, {str(hostfile)!r}, {stage!r})"
                    )
                    children.append(
                        subprocess.Popen(
                            [sys.executable, "-c", code],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                    )
                for child in children:
                    stdout, stderr = child.communicate(
                        timeout=max(0.01, deadline - time.monotonic())
                    )
                    print(stdout, end="", flush=True)
                    assert child.returncode == 7, stderr
            finally:
                for child in children:
                    if child.poll() is None:
                        _kill_process_tree(child.pid)
                for child in children:
                    child.communicate(timeout=1)
    print("Actual two-rank capability/eviction/divergence gates passed", flush=True)


if __name__ == "__main__":
    main()
