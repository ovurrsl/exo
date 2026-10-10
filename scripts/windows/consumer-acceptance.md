# Windows runtime acceptance without a separate Python installation

Extract this kit on the Windows machine being tested. Install the reviewed EXO
candidate first. Supply previously downloaded, pinned model snapshots, including
their `.cache/huggingface/download` or `.exo-revisions` metadata. No weights are
included in this kit. The default chat model is `mlx-community/Qwen3-0.6B-4bit`.

Run from PowerShell, replacing each path with the actual installed runtime,
read-only model root, new evidence directory and real safetensors shard:

```powershell
./check-installed-runtime.ps1 `
  -RuntimeDirectory 'C:\Users\NAME\AppData\Local\Programs\EXO\runtime' `
  -ModelDirectory 'D:\verified-models' `
  -OutputDirectory 'C:\exo-acceptance\new-run' `
  -LargeModelShard 'D:\verified-models\Qwen3-VL\model.safetensors'
```

The shard must be larger than 2 GiB. The script uses the installed `exo.exe`
interpreter and its bundled libraries; Python, uv, Node, Rust, Visual Studio and
the CUDA Toolkit are not required. A compatible NVIDIA driver is required.
Keep all kit files, including `kit-manifest.json`, together. Compare the ZIP's
SHA-256 with the reviewed artifact before extraction. The script checks every
helper against the manifest before execution; this detects changed or mixed kit
files. The manifest is unsigned and is not independent proof of publisher identity.
If local script execution policy requires it,
review these scripts first and use a process-scoped policy; do not change the
machine-wide policy. No administrator elevation is required by the kit.

The script rejects an existing evidence directory, linked paths, overlapping
model/runtime paths and an engine hash that differs from the runtime manifest.
It checks the complete runtime before and after GPU gates and HTTP inference.
The GPU gates include kernel/JIT/spawn, local ring and the real large shard.
Chat includes repeated prompts, a longer context, streaming cancellation,
recovery and normal spawned-worker shutdown. Inference uses a private namespace,
test ports and a separate data directory. These test ports do not change the
application's default API port, 52415. Models are read only. Active EXO processes
and the installed desktop application's settings are not controlled by the kit.

Installed developer tools are detected from PATH commands, uninstall registrations
and CUDA environment variables. This bounded inventory cannot prove absence of
all portable tools on disk. `-AllowDeveloperMachine` permits a local smoke test
but always leaves `clean_windows_runtime_acceptance_passed=false`.
`-PreflightOnly` verifies paths and engine identity without executing it; it
does not claim GPU/inference or full-file integrity acceptance.

Inspect `installed-runtime.json`, `runtime-gates.json`, `inference/inference.json`
and the logs. `passed=true` means these runtime gates passed. On a clean system,
`clean_windows_runtime_acceptance_passed=true` records the bounded clean-runtime
gate. Overall `clean_windows_acceptance_passed` and `release_ready` remain false:
installation/uninstallation, native tray/WebView/DPI/keyboard behavior, signed
updates, security review and physical Mac cluster tests need separate evidence.
