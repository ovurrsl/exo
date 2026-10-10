"""Exercise a real isolated EXO node and its spawned CUDA runner through HTTP.

This is a hardware acceptance command, not a mocked unit test. It never joins
the user's namespace or writes into their model directory.
"""

import argparse
import base64
import contextlib
import ctypes
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import httpx


def available_port() -> int:
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="mlx-community/Qwen3-0.6B-4bit")
    parser.add_argument("--vision", action="store_true")
    parser.add_argument("--exercise-cancel", action="store_true")
    parser.add_argument("--ram-offload", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--request-timeout", type=float, default=90)
    parser.add_argument("--runner-ready-timeout", type=float, default=120)
    parser.add_argument("--cancel-timeout", type=float, default=20)
    arguments = parser.parse_args()
    if (
        min(
            arguments.max_tokens,
            arguments.request_timeout,
            arguments.runner_ready_timeout,
            arguments.cancel_timeout,
        )
        <= 0
    ):
        parser.error("Token and timeout limits must be positive")
    if arguments.ram_offload and arguments.vision:
        parser.error("Experimental RAM offload does not support vision")
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    api_port = available_port()
    environment = {
        **os.environ,
        "EXO_HOME": str(output / "node-data"),
        "EXO_MODELS_READ_ONLY_DIRS": str(arguments.model_dir.resolve()),
        "EXO_OFFLINE": "true",
        "PYTHONUTF8": "1",
    }
    if arguments.ram_offload:
        environment["EXO_WINDOWS_TEXT_OFFLOAD"] = "true"
    executable = (
        [str(arguments.runtime)] if arguments.runtime else [sys.executable, "-m", "exo"]
    )
    executable += [
        "--namespace",
        f"acceptance-{uuid.uuid4().hex}",
        "--force-master",
        "--api-port",
        str(api_port),
        "--zenoh-port",
        str(available_port()),
        "--discovery-port",
        str(available_port()),
        "--offline",
        "--no-downloads",
    ]
    model = arguments.model
    report = {"model": model, "runtime": executable[0], "chats": [], "passed": False}
    if arguments.ram_offload:
        from exo.utils.windows_gpu import read_gpu_memory

        try:
            snapshot = arguments.model_dir.resolve() / model.replace("/", "--")
            index = json.loads((snapshot / "model.safetensors.index.json").read_text())
            tensor_bytes = int(index["metadata"]["total_size"])
            if any(
                not (snapshot / shard).is_file()
                for shard in set(index["weight_map"].values())
            ):
                raise RuntimeError("RAM offload acceptance requires every model shard")
            gpu = read_gpu_memory()
            if gpu is None or tensor_bytes <= gpu.total.in_bytes:
                raise RuntimeError(
                    "RAM offload acceptance requires weights larger than real dedicated VRAM"
                )
            report["ram_offload"] = {
                "model_tensor_bytes": tensor_bytes,
                "gpu_total_bytes": gpu.total.in_bytes,
            }
        except Exception as exc:
            report["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "phase": "preflight",
            }
            (output / "inference.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            raise
    # Preflight must finish before creating resources requiring cleanup.
    event = None
    kernel = None
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateEventW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_wchar_p,
        ]
        kernel.CreateEventW.restype = ctypes.c_void_p
        kernel.SetEvent.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        event_name = f"Local\\exo-shutdown-{uuid.uuid4().hex}"
        event = kernel.CreateEventW(None, 1, 0, event_name)
        if not event:
            raise ctypes.WinError()
        environment["EXO_WINDOWS_SHUTDOWN_EVENT"] = event_name
    with (output / "node.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            executable,
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        sampling_stop = threading.Event()
        sampling_thread = None
        if arguments.ram_offload:
            import psutil

            profile = {
                "samples": 0,
                "peak_process_tree_rss_bytes": 0,
                "peak_system_gpu_used_bytes": 0,
                "min_system_host_available_bytes": int(
                    psutil.virtual_memory().available
                ),
            }
            report["ram_offload"]["memory_profile"] = profile

            def sample_memory() -> None:
                while not sampling_stop.is_set():
                    try:
                        parent = psutil.Process(process.pid)
                        processes = [parent, *parent.children(recursive=True)]
                        rss = 0
                        for owned in processes:
                            with contextlib.suppress(psutil.Error):
                                rss += owned.memory_info().rss
                        profile["peak_process_tree_rss_bytes"] = max(
                            profile["peak_process_tree_rss_bytes"], rss
                        )
                        profile["min_system_host_available_bytes"] = min(
                            profile["min_system_host_available_bytes"],
                            int(psutil.virtual_memory().available),
                        )
                        memory = read_gpu_memory()
                        if memory is not None:
                            used = memory.total.in_bytes - memory.free.in_bytes
                            profile["peak_system_gpu_used_bytes"] = max(
                                profile["peak_system_gpu_used_bytes"], used
                            )
                        profile["samples"] += 1
                    except psutil.Error:
                        break
                    sampling_stop.wait(0.25)

            sampling_thread = threading.Thread(target=sample_memory, daemon=True)
            sampling_thread.start()
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{api_port}",
                timeout=arguments.request_timeout,
            ) as client:
                deadline = time.monotonic() + 60
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(
                            f"EXO exited before readiness: {process.returncode}"
                        )
                    try:
                        response = client.get("/state", timeout=2)
                        response.raise_for_status()
                        state = response.json()
                        if any(
                            "MlxCuda" in backends
                            for backends in state.get("nodeBackends", {}).values()
                        ):
                            report["node_memory"] = state.get("nodeMemory")
                            break
                    except (httpx.HTTPError, ValueError):
                        pass
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "CUDA node did not become ready within 60 seconds"
                        )
                    time.sleep(0.25)
                if arguments.ram_offload:
                    capacity = client.get("/windows/model-capacity")
                    capacity.raise_for_status()
                    qualification = capacity.json().get("models", {}).get(model)
                    report["ram_offload"]["qualification"] = qualification
                    if not qualification or qualification["mode"] != "ram_offload":
                        raise RuntimeError(
                            "Node did not qualify the oversized model for RAM offload"
                        )
                response = client.post("/place_instance", json={"model_id": model})
                response.raise_for_status()
                deadline = time.monotonic() + arguments.runner_ready_timeout
                while True:
                    state = client.get("/state").json()
                    statuses = list(state.get("runners", {}).values())
                    if any("RunnerFailed" in status for status in statuses):
                        raise RuntimeError(f"Runner failed: {statuses}")
                    if statuses and all("RunnerReady" in status for status in statuses):
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"Spawned runner did not load/warm up within {arguments.runner_ready_timeout} seconds"
                        )
                    time.sleep(0.25)
                prompts = (
                    "Reply with hello.",
                    "What is two plus two? Reply briefly.",
                )
                vision_content = None
                if arguments.vision:
                    from PIL import Image

                    pixels = io.BytesIO()
                    Image.new("RGB", (112, 112), (255, 0, 0)).save(pixels, format="PNG")
                    vision_content = [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(pixels.getvalue()).decode()
                            },
                        },
                        {
                            "type": "text",
                            "text": "What color is this image? Reply with one word.",
                        },
                    ]
                    prompts = ("What color is this image?",) * 2
                elif arguments.exercise_cancel:
                    prompts += (
                        "Context: "
                        + "A small red apple rests on a wooden table. " * 120
                        + "Reply with the color of the apple.",
                    )
                for prompt in prompts:
                    response = client.post(
                        "/v1/chat/completions",
                        json={
                            "model": model,
                            "messages": [
                                {"role": "user", "content": vision_content or prompt}
                            ],
                            "max_tokens": arguments.max_tokens,
                            "temperature": 0,
                            "enable_thinking": False,
                            "use_prefix_cache": True,
                        },
                    )
                    response.raise_for_status()
                    completion = response.json()
                    if not completion.get("choices"):
                        raise RuntimeError("No completion choices returned")
                    if (
                        arguments.vision
                        and "red"
                        not in completion["choices"][0]["message"]
                        .get("content", "")
                        .lower()
                    ):
                        raise RuntimeError(
                            "Vision completion did not identify the red image"
                        )
                    report["chats"].append(completion)
                if arguments.exercise_cancel:
                    with client.stream(
                        "POST",
                        "/v1/chat/completions",
                        json={
                            "model": model,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Write a numbered list of 1000 different animals. Keep writing until the list is finished.",
                                }
                            ],
                            "stream": True,
                            "max_tokens": 2048,
                            "enable_thinking": False,
                        },
                    ) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line.startswith("data: ") and line != "data: [DONE]":
                                chunk = json.loads(line.removeprefix("data: "))
                                if (
                                    chunk.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content")
                                ):
                                    break
                        else:
                            raise RuntimeError(
                                "No streaming token was returned before cancellation"
                            )
                    deadline = time.monotonic() + arguments.cancel_timeout
                    while True:
                        statuses = list(
                            client.get("/state").json().get("runners", {}).values()
                        )
                        if statuses and all(
                            "RunnerReady" in status for status in statuses
                        ):
                            break
                        if time.monotonic() > deadline:
                            raise TimeoutError(
                                "Cancellation did not recover to RunnerReady"
                            )
                        time.sleep(0.25)
                    recovered = client.post(
                        "/v1/chat/completions",
                        json={
                            "model": model,
                            "messages": [
                                {"role": "user", "content": "Reply with hello."}
                            ],
                            "max_tokens": min(16, arguments.max_tokens),
                            "enable_thinking": False,
                        },
                    )
                    recovered.raise_for_status()
                    if not recovered.json().get("choices"):
                        raise RuntimeError("No completion after cancellation")
                    report["cancel_recovery"] = recovered.json()
                report["passed"] = True
        except Exception as exc:
            report["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "phase": "inference",
            }
            raise
        finally:
            sampling_stop.set()
            if sampling_thread is not None:
                sampling_thread.join(timeout=2)
            if process.poll() is None:
                if kernel is not None:
                    kernel.SetEvent(event)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True,
                            check=False,
                        )
                    else:
                        process.kill()
                    process.wait(timeout=5)
                    report["passed"] = False
                    report["shutdown_error"] = "Forced cleanup was required"
            report["exit_code"] = process.returncode
            if process.returncode != 0:
                report["passed"] = False
            if kernel is not None:
                kernel.CloseHandle(event)
            if process.returncode == 0:
                log.flush()
                # Native libraries can write console-codepage bytes directly to
                # the redirected handle even when Python itself uses UTF-8.
                # Match ASCII lifecycle markers without rejecting those messages.
                shutdown_log = (output / "node.log").read_text(
                    encoding="utf-8", errors="replace"
                )
                if (
                    "Child process didn't shut down successfully" in shutdown_log
                    or "Runner process successfully terminated: 0" not in shutdown_log
                ):
                    report["passed"] = False
                    report["shutdown_error"] = (
                        "The inference worker did not exit normally"
                    )
            (output / "inference.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    if not report["passed"]:
        raise SystemExit(1)
    print(
        f"EXO CUDA HTTP inference and graceful spawned-runner shutdown passed: {output}"
    )


if __name__ == "__main__":
    main()
