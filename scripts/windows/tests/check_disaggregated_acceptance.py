"""Offline real CUDA prefill, TCP cache transfer and resumed decode gate."""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from queue import Queue
from threading import Event


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path", type=Path)
    arguments = parser.parse_args()
    path = arguments.model_path.resolve()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from exo.utils.rlimits import install_windows_resource_shim

    install_windows_resource_shim()
    import mlx.core as mx
    from mlx_lm.generate import generate_step
    from mlx_lm.utils import load

    from exo.worker.disaggregated.server import PrefillRequest, PrefillServer
    from exo.worker.engines.mlx.cache import KVPrefixCache, cache_length, make_kv_cache
    from exo.worker.engines.mlx.disaggregated.adapter import (
        array_to_bytes,
        write_cache_to_wire,
    )
    from exo.worker.engines.mlx.disaggregated.client import (
        ingest_into_mlx_cache,
        remote_prefill_fetch,
    )
    from exo.worker.engines.mlx.disaggregated.serve import run_prefill_for_request

    assert mx.cuda.is_available(), "A real CUDA device is required"
    mx.set_default_device(mx.gpu)
    model, tokenizer = load(path)
    prompt = tokenizer.apply_chat_template(
        [
            {
                "role": "user",
                "content": "Context: "
                + "A small apple is red. " * 64
                + "What color is the apple? Reply with one word.",
            }
        ],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    prefix = KVPrefixCache(None, cuda_group=True)
    pending = Queue()

    def resolve(request, stream):
        # Match Runner's production ownership: handler queues the wire request,
        # while the main runner thread owns every model/cache/CUDA operation.
        done = Event()
        pending.put((request, stream, done))
        return done.wait(15)

    server = PrefillServer(resolve, "127.0.0.1", 0)
    reports = []
    try:
        endpoint = f"127.0.0.1:{server.server_address[1]}"
        for start_pos in (0, 32):
            with ThreadPoolExecutor(max_workers=1) as clients:
                fetched = clients.submit(
                    remote_prefill_fetch,
                    endpoint,
                    PrefillRequest(
                        request_id=f"cuda-transfer-{start_pos}",
                        model_id=path.name,
                        token_ids=prompt,
                        start_pos=start_pos,
                    ),
                    timeout_secs=15,
                )
                request, stream, done = pending.get(timeout=15)
                try:
                    source = run_prefill_for_request(
                        model=model,
                        tokenizer=tokenizer,
                        group=None,
                        kv_prefix_cache=prefix,
                        request=request,
                    )
                    mx.eval([entry.state for entry in source])
                    write_cache_to_wire(
                        stream,
                        source,
                        request_id=request.request_id,
                        model_id=request.model_id,
                        start_pos=request.start_pos,
                    )
                finally:
                    done.set()
                result = fetched.result(timeout=15)
            destination = make_kv_cache(model)
            print(
                f"transfer {start_pos}: fetched {result.total_tokens} tokens",
                flush=True,
            )
            if start_pos:
                for src, dst in zip(source, destination, strict=True):
                    dst.keys = mx.array(src.keys[:, :, :start_pos, :])
                    dst.values = mx.array(src.values[:, :, :start_pos, :])
                    dst.offset = start_pos
            final_offset = ingest_into_mlx_cache(
                result, destination, start_pos=start_pos
            )
            print(f"transfer {start_pos}: ingested at {final_offset}", flush=True)
            assert 0 < final_offset < len(prompt)
            assert final_offset == cache_length(source)
            assert len(result.kv_chunks) == len(model.layers)
            for src, dst in zip(source, destination, strict=True):
                for left, right in ((src.keys, dst.keys), (src.values, dst.values)):
                    assert left.dtype == right.dtype
                    assert array_to_bytes(
                        left[:, :, :final_offset, :]
                    ) == array_to_bytes(right), (
                        "CUDA cache values changed during CPU/TCP transfer"
                    )
            mx.eval([entry.state for entry in destination])
            print(f"transfer {start_pos}: byte parity verified", flush=True)
            resumed = [
                int(token)
                for token, _ in generate_step(
                    mx.array(prompt[final_offset:]),
                    model,
                    prompt_cache=destination,
                    max_tokens=8,
                )
            ]
            baseline = [
                int(token)
                for token, _ in generate_step(mx.array(prompt), model, max_tokens=8)
            ]
            assert resumed == baseline, "Transferred cache changed greedy decode tokens"
            reports.append(
                {
                    "start_pos": start_pos,
                    "prefill_tokens": final_offset,
                    "wire_tokens": result.total_tokens,
                    "layers": len(result.kv_chunks),
                    "dtype": result.header.dtype,
                    "decode_tokens": resumed,
                    "response": tokenizer.decode(resumed),
                    "matches_fresh_prefill": True,
                }
            )
    finally:
        server.stop()
    print(
        json.dumps(
            {
                "mlx_version": version("mlx"),
                "prompt_tokens": len(prompt),
                "transfers": reports,
                "peak_gpu_bytes": mx.get_peak_memory(),
                "scope": "Windows CUDA prefill/TCP/ingest/decode; no physical Mac peer",
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            json.dumps({"error": type(error).__name__, "detail": str(error)}),
            flush=True,
        )
        raise
