"""Real isolated Windows CUDA image placement, HTTP and worker-exit gate."""

import argparse
import base64
import ctypes
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
from check_inference import available_port
from PIL import Image

MODEL = "exolabs/FLUX.1-schnell-4bit"
GPU_WEIGHT_BYTES = 6_693_214_336


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--exercise-edit",
        action="store_true",
        help="Also qualify single-CUDA Schnell img2img input conditioning and recovery",
    )
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("This qualification gate requires physical Windows CUDA")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    port = available_port()
    event_name = f"Local\\exo-shutdown-{uuid.uuid4().hex}"
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
    event = kernel.CreateEventW(None, 1, 0, event_name)
    if not event:
        raise ctypes.WinError()
    command = [str(args.runtime)] if args.runtime else [sys.executable, "-m", "exo"]
    command += [
        "--namespace",
        f"image-acceptance-{uuid.uuid4().hex}",
        "--force-master",
        "--offline",
        "--no-downloads",
        "--api-port",
        str(port),
        "--zenoh-port",
        str(available_port()),
        "--discovery-port",
        str(available_port()),
    ]
    environment = {
        **os.environ,
        "EXO_HOME": str(output / "node-data"),
        "EXO_MODELS_READ_ONLY_DIRS": str(args.model_dir.resolve()),
        "EXO_ENABLE_IMAGE_MODELS": "true",
        "EXO_WINDOWS_SHUTDOWN_EVENT": event_name,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONUTF8": "1",
    }
    report = {"model": MODEL, "runtime": command[0], "passed": False, "images": []}
    with (output / "node.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=240, trust_env=False
            ) as client:

                def state_when(predicate, timeout: float):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise RuntimeError(f"EXO exited: {process.returncode}")
                        try:
                            response = client.get("/state", timeout=2)
                            response.raise_for_status()
                            state = response.json()
                            if any(
                                "RunnerFailed" in status
                                for status in state.get("runners", {}).values()
                            ):
                                raise RuntimeError(
                                    f"Image runner failed: {state['runners']}"
                                )
                            if predicate(state):
                                return state
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.25)
                    raise TimeoutError("Image node/runner failed to make progress")

                state_when(
                    lambda state: any(
                        "MlxCuda" in backend
                        for backend in state.get("nodeBackends", {}).values()
                    ),
                    60,
                )
                response = client.get("/instance/previews", params={"model_id": MODEL})
                response.raise_for_status()
                previews = [
                    preview
                    for preview in response.json()["previews"]
                    if preview.get("instance")
                ]
                preview = next(
                    preview
                    for preview in previews
                    if "MlxRingInstance" in preview["instance"]
                    and len(
                        preview["instance"]["MlxRingInstance"]["shardAssignments"][
                            "nodeToRunner"
                        ]
                    )
                    == 1
                )
                delta = preview.get(
                    "memoryDeltaByNode", preview.get("memory_delta_by_node")
                )
                assert delta and list(delta.values()) == [GPU_WEIGHT_BYTES], delta
                report["preview"] = preview
                response = client.post(
                    "/instance", json={"instance": preview["instance"]}
                )
                response.raise_for_status()
                state_when(
                    lambda state: bool(state.get("runners"))
                    and all(
                        "RunnerReady" in status for status in state["runners"].values()
                    ),
                    400,
                )

                def generate(
                    label: str, cancel: bool = False, edit: bytes | None = None
                ):
                    received = []
                    payload = {
                        "model": MODEL,
                        "prompt": "A red apple on a white background",
                        "size": "512x512",
                        "n": 1,
                        "stream": True,
                        "partial_images": 1,
                        "response_format": "b64_json",
                        "advanced_params": {"seed": 2, "num_inference_steps": 4},
                    }
                    if edit is None:
                        endpoint = "/v1/images/generations"
                        request = {"json": payload}
                    else:
                        endpoint = "/v1/images/edits"
                        request = {
                            "files": {"image": ("input.png", edit, "image/png")},
                            "data": {
                                "model": MODEL,
                                "prompt": payload["prompt"],
                                "size": "512x512",
                                "n": "1",
                                "stream": "true",
                                "partial_images": "1",
                                "response_format": "b64_json",
                                "input_fidelity": "high",
                                "advanced_params": json.dumps(
                                    payload["advanced_params"]
                                ),
                            },
                        }
                    with client.stream(
                        "POST",
                        endpoint,
                        **request,
                    ) as stream:
                        stream.raise_for_status()
                        for line in stream.iter_lines():
                            if not line.startswith("data: ") or line == "data: [DONE]":
                                continue
                            value = json.loads(line[6:])
                            if "error" in value:
                                raise RuntimeError(value["error"])
                            kind = value.get("type")
                            if kind not in ("partial", "final"):
                                continue
                            data = base64.b64decode(
                                value["data"]["b64_json"], validate=True
                            )
                            image = Image.open(io.BytesIO(data))
                            image.load()
                            assert image.size == (512, 512)
                            assert float(np.asarray(image).std()) > 1
                            path = output / f"{label}-{kind}.png"
                            path.write_bytes(data)
                            received.append(
                                {
                                    "type": kind,
                                    "sha256": hashlib.sha256(data).hexdigest(),
                                    "size": image.size,
                                    "path": str(path),
                                }
                            )
                            if cancel:
                                assert kind == "partial", (
                                    "Cancellation must follow an actual denoise/partial decode"
                                )
                                break
                    if cancel:
                        assert received, (
                            "Cancellation never reached a real partial image"
                        )
                    else:
                        assert [item["type"] for item in received] == [
                            "partial",
                            "final",
                        ]
                    report["images"].append({"label": label, "events": received})
                    state_when(
                        lambda state: bool(state.get("runners"))
                        and all(
                            "RunnerReady" in status
                            for status in state["runners"].values()
                        ),
                        30,
                    )

                generate("initial")
                generate("cancel", cancel=True)
                generate("recovered")
                if args.exercise_edit:
                    fixture = io.BytesIO()
                    Image.new("RGB", (512, 512), (220, 30, 30)).save(
                        fixture, format="PNG"
                    )
                    red = fixture.getvalue()
                    fixture = io.BytesIO()
                    Image.new("RGB", (512, 512), (30, 30, 220)).save(
                        fixture, format="PNG"
                    )
                    blue = fixture.getvalue()
                    generate("edit-red", edit=red)
                    generate("edit-blue", edit=blue)
                    generate("edit-cancel", cancel=True, edit=red)
                    generate("edit-recovered", edit=red)
                    finals = {
                        record["label"]: record["events"][-1]["sha256"]
                        for record in report["images"]
                        if record["events"][-1]["type"] == "final"
                    }
                    assert finals["edit-red"] != finals["edit-blue"], (
                        "Input images were ignored"
                    )
                    assert finals["edit-red"] == finals["edit-recovered"], (
                        "Edit cancellation changed subsequent same-seed output"
                    )
                    report["edit_scope"] = "single-CUDA-Schnell-img2img-no-mask"
                    report["different_input_changes_output"] = True
                    report["edit_cancel_recovery_deterministic"] = True
                report["passed"] = True
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "detail": str(error)}
            raise
        finally:
            if process.poll() is None:
                kernel.SetEvent(event)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                    process.wait(timeout=5)
                    report["passed"] = False
                    report["shutdown_error"] = "Owned node tree required forced cleanup"
            kernel.CloseHandle(event)
            log.flush()
            shutdown_log = (output / "node.log").read_text(
                encoding="utf-8", errors="replace"
            )
            report["exit_code"] = process.returncode
            if (
                process.returncode != 0
                or "Child process didn't shut down successfully" in shutdown_log
                or "Runner process successfully terminated: 0" not in shutdown_log
            ):
                report["passed"] = False
                report["shutdown_error"] = "Image node/worker did not exit normally"
            (output / "inference.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    if not report["passed"]:
        raise SystemExit(1)
    print(
        f"Real CUDA image preview/create/partial/cancel/recovery and worker exit passed: {output}"
    )


if __name__ == "__main__":
    main()
