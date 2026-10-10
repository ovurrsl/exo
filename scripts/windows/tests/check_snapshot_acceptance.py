"""Offline two-rank CPU-ring snapshot contract hardware gate."""

import argparse
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


def worker(model_path: str, rank: int, hostfile: str, stage: str) -> None:
    path = Path(model_path)
    model_id_value = path.name.replace("--", "/", 1)
    os.environ["EXO_MODELS_READ_ONLY_DIRS"] = str(path.parent)
    os.environ["EXO_HOME"] = str(path.parent / "contract-acceptance-home")
    os.environ["MLX_RANK"] = str(rank)
    os.environ["MLX_HOSTFILE"] = hostfile
    from exo.utils.rlimits import install_windows_resource_shim

    install_windows_resource_shim()
    import mlx.core as mx

    from exo.shared.models.model_cards import ConfigData, ModelCard, ModelTask
    from exo.shared.types.backends import Backend
    from exo.shared.types.common import ModelId, NodeId
    from exo.shared.types.memory import Memory
    from exo.shared.types.worker.instances import (
        BoundInstance,
        InstanceId,
        MlxRingInstance,
    )
    from exo.shared.types.worker.runners import RunnerId, ShardAssignments
    from exo.shared.types.worker.shards import PipelineShardMetadata
    from exo.worker.engines.mlx.snapshot_guard import verify_cuda_group_contract

    model_id = ModelId(model_id_value)
    config = ConfigData.model_validate_json(
        (path / "config.json").read_text(encoding="utf-8"),
        context={"model_id": model_id_value},
    )
    card = ModelCard(
        model_id=model_id,
        storage_size=Memory.from_mb(512),
        n_layers=config.layer_count,
        hidden_size=config.hidden_size or 1024,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxCuda],
        quantization="different" if stage == "mismatch" and rank == 1 else "4bit",
    )
    runners = [RunnerId(f"runner-{index}") for index in range(2)]
    nodes = [NodeId(f"node-{index}") for index in range(2)]
    assignments = ShardAssignments(
        model_id=model_id,
        runner_to_shard={
            runners[index]: PipelineShardMetadata(
                model_card=card,
                device_rank=index,
                world_size=2,
                start_layer=config.layer_count * index // 2,
                end_layer=config.layer_count * (index + 1) // 2,
                n_layers=config.layer_count,
            )
            for index in range(2)
        },
        node_to_runner=dict(zip(nodes, runners, strict=True)),
    )
    bound = BoundInstance(
        instance=MlxRingInstance(
            instance_id=InstanceId("snapshot-acceptance"),
            shard_assignments=assignments,
            hosts_by_node={},
            ephemeral_port=0,
        ),
        bound_runner_id=runners[rank],
        bound_node_id=nodes[rank],
    )
    group = mx.distributed.init(strict=True, backend="ring")
    expected_rejection = stage != "valid"
    try:
        if stage == "local-error" and rank == 1:
            with mock.patch(
                "exo.worker.engines.mlx.snapshot_guard.build_model_path",
                return_value=path / "missing-snapshot",
            ):
                verify_cuda_group_contract(bound, group)
        else:
            verify_cuda_group_contract(bound, group)
    except RuntimeError as error:
        if not expected_rejection:
            raise
        print(f"rank {rank}: {stage} rejected collectively: {error}", flush=True)
    else:
        assert not expected_rejection, f"Rank {rank} accepted {stage}"
        print(f"rank {rank}: actual pinned snapshot contract verified", flush=True)
    sys.exit(7)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path", type=Path)
    arguments = parser.parse_args()
    path = arguments.model_path.resolve()
    print(f"Snapshot contract gate using MLX {version('mlx')}", flush=True)
    for stage in ("valid", "mismatch", "local-error"):
        children: list[subprocess.Popen[str]] = []
        with TemporaryDirectory(
            prefix="exo-contract-gate-", dir=Path.cwd()
        ) as temporary:
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
                        "from scripts.windows.tests.check_snapshot_acceptance import worker; "
                        f"worker({str(path)!r}, {rank}, {str(hostfile)!r}, {stage!r})"
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
    print("Actual two-rank contract success/mismatch/local-IO gates passed", flush=True)


if __name__ == "__main__":
    main()
