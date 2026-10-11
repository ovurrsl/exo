# Windows model capacity and experimental RAM offload

**Quality qualification update (11 October):** the earlier oversized-model
acceptance below exercised fixed prompts at temperature zero. It does not qualify
normal sampled multilingual chat. A real BF16 CPU output-head numerical regression
has since been reproduced; VRAM residency is also incomplete. See the
[research and correction plan](windows-vram-first-quality-research-20261010.md).

The model picker keeps the existing Mac layout and palette. On a single Windows
CUDA node, normal dedicated-VRAM capacity is green; qualified experimental RAM
offload is yellow with an explicit `RAM offload` label; insufficient or unsupported
capacity is red. RAM-qualified entries remain in the loadable and downloadable
lists. Existing image-stage estimates retain precedence. Older servers, Mac-only
and mixed clusters retain the existing estimator.

The private `/windows/model-capacity` endpoint does not change shared event/state
schemas. It reports ordinary VRAM fit first, then validates opt-in offload against
separate available host RAM and dedicated VRAM budgets. Host RAM is never added to
the advertised CUDA memory. Both placement and loading recheck capacity.

## Experimental scope

Offload requires `EXO_WINDOWS_TEXT_OFFLOAD=true`. It currently supports only one
local Windows CUDA runner, a full dense Qwen3 text model, affine 4-bit quantization
with group size 32 or 64, batch size one, bounded prefill and context. Decoder
weights are staged one layer at a time. Embedding, norm and output-head work stays
on the CPU. Missing model files or tensors fail strict loading. Unsupported vision,
MoE, Qwen3.5, distributed and tensor-parallel paths are not qualified.

Normal models that fit dedicated VRAM retain the ordinary GPU loading path.
Offload remains opt-in after acceptance on an actual >12 GB model. Thus the
yellow label is a qualified experimental mode, not a claim that
every model fitting physical RAM is supported or that performance equals VRAM.

## Verification and remaining work

- Python regression after security, performance and catalog corrections: 798 passed,
  8 skipped, 195 deselected. These counts do not treat skipped tests as acceptance.
- Full Windows and Darwin Python type checks: zero errors. Ruff check and format
  check passed (335 files). Nix is unavailable on this Windows machine.
- Real CUDA FP32 and BF16 staging/logit/KV parity and failure cleanup passed.
- Dashboard production build passed. Svelte check has the same 15 errors and six
  warnings as the unchanged baseline; no new diagnostics were introduced.
- All 18 dashboard capacity/image-fit/render tests passed, including actual Svelte
  picker markup for green VRAM fit, yellow RAM offload, red insufficient capacity,
  and individual labels in expanded multi-variant groups. Prettier check passed.
- `mlx-community/Qwen3-32B-4bit` revision
  `bcaaf7f538adf166c1080a2befdb4f6019f66639` was selected for large-model acceptance
  (18,429,667,328 tensor bytes). Download completed; all four large shards passed
  their pinned LFS SHA-256 checks. Both source and self-contained frozen HTTP
  acceptance passed: three chats, a 1,222-token input, cancellation followed by
  another successful chat, and normal runner/node exit (code 0).
- The corrected runtime was rebuilt from production commit
  `1d357a6061b3e359616aefe9767118d99c6fbb69`. Its 32 frozen runtime gates passed,
  including GPU/CPU computation, spawned processes, Unicode paths, a real
  5.346 GB safetensors file, and local two/three/four-process ring checks.
  These local ring checks do not establish Mac/Windows cluster acceptance.
- An unsigned review installer was built successfully. Clean installation
  on a Windows machine without development tools, signing, and release/update
  publication remain pending.
- Mac clustering remains deferred as requested. No Mac Swift files were changed.

## Restricted loader security correction

The opt-in loader previously called MLX before checking the concrete model type.
MLX can execute a snapshot's `model_file` during that call. A harmless local marker
test reproduced execution before rejection. The restricted loader now requires a
flat built-in `qwen3` configuration and rejects any `model_file` field before
loading. Explicit dispatch overrides also protect MLX's subsequent config reread.
Its separate tokenizer loader forces `trust_remote_code=False` and bypasses
model-ID-driven custom Python imports. Existing normal and distributed loaders
retain their prior paths; the newly introduced 32B card explicitly declines remote
code as well.

Regression coverage includes custom and parent-relative paths, non-object and
unsupported configurations, config replacement between validation and use,
tokenizer `auto_map`, and an offload card whose ID otherwise triggers Kimi imports.
The malicious marker no longer appears. Real Qwen3-0.6B still produces `Hello!`
with EOS 151645 and 112 opened/closed stages, no active stage remaining. Independent
read-only investigation and candidate review found no surviving snapshot-Python
route in this restricted branch. This is scoped remediation, not a repository-wide
security audit. The earlier c31 package evidence does not certify this source;
the corrected runtime has its own source freeze and repeated frozen gates.

## Large-model performance correction

The first 32B source run loaded successfully in 37.4 seconds but spent 120.56
seconds in warmup prefill. A read-only CPU sample confirmed active computation,
not a stalled peer: the wrapper eagerly evaluated its CPU vocabulary projection
even for intermediate prefill logits that MLX discards. The corrected wrapper
keeps that projection and its final GPU copy lazy, while still evaluating decoder
output and KV state and synchronizing before restoring each staged weight set.
Only offloaded models use a two-token warmup; ordinary models retain 50 tokens.

In the subsequent local run, the same warmup prefill took 17.33 seconds and the
runner became ready in 76.57 seconds including loading. This is a single local
comparison, not a general throughput guarantee. Discarded-logit and warmup
regressions pass; both real CUDA FP32 and BF16 logits/KV parity tests also pass.
The first acceptance run was deliberately interrupted and is not a passed test.
The corrected source and self-contained frozen runs both completed HTTP inference
and cancellation/recovery. The frozen run cleared development resource, dashboard
and Python path overrides, so it exercised bundled assets. An earlier frozen run
with inherited development overrides was interrupted and is not a passed test.

## Oversized-model measured acceptance

The frozen report is
`build/acceptance/qwen3-32b-ram-offload-self-contained-frozen-20261010/inference.json`.
It records 18,429,667,328 model tensor bytes against 12,820,938,752 physical GPU
bytes. Peak owned process-tree RSS was 20,986,691,584 bytes (19.55 GiB); minimum
available system RAM was 6,367,793,152 bytes. Peak **system-wide** GPU usage was
2,855,944,192 bytes, including desktop/other GPU users; this is not an exclusive
EXO allocation measurement. Capacity qualified the model as `ram_offload`.

Observed replies included `4` for the arithmetic prompt and `The color of the
apple is red.` after the long input. Cancellation recovery produced another
valid greeting. These short fixed-input checks establish functionality on this
RTX 5070/48 GiB machine, not universal model compatibility or quality evaluation.
CPU projection and repeated staging make generation substantially slower than
fully resident GPU inference (approximately 0.11 token/s in the source short-chat
sample). Longer contexts and other architectures require separate qualification.

## Catalog admission correction after desktop verification

Live desktop API verification exposed an unsupported MoE entry incorrectly
labelled `ram_offload`: the existing Qwen3-30B-A3B card uses the generic base name
`Qwen3 30B`. Numeric family-name matching was insufficient. Admission now limits
the experimental path to known dense Qwen3 base sizes; catalog 30B/235B expert
models cannot qualify for staging. Models that genuinely fit VRAM retain the
ordinary path. Regression coverage verifies both placement admission and the
private capacity response. Strict actual architecture validation remains in the
loader, so a custom misleading card cannot bypass loading checks.

The earlier 1d357 runtime's successful 32B inference remains evidence for that
unchanged inference path, but its desktop MoE label is superseded. The corrected
runtime from `417be25981f52d1e0875ea68dafb5f67fb1604ab` was rebuilt and validated:
all 32 frozen gates passed again, 160 collected EXO modules originated in this
worktree, and 11,441 runtime files passed validation. Default offload remains off.

Runtime executable SHA-256:
`585f83ce95a8ecca83a831f612b913d64e049329db2b34a3c872bb4fdee09761`.
Manifest SHA-256:
`e91d549e2b5a11401cad89929cd326b61f80c6c8553be31f98af305437d9528d`.
The manifest explicitly records `release_ready=false`.

The review desktop was launched with this corrected runtime via
`EXO_RUNTIME_DIR`. Its live API at port 52415 reported Qwen3-32B as `ram_offload`,
Qwen3-0.6B as `vram`, and Qwen3-30B-A3B as `unavailable`, after initial GPU
discovery. Existing user settings were backed up before enabling offload and
adding the acceptance model directory as read-only. The local test namespace is
`windows-ram-local`; Mac clustering remains deferred.

## Corrected review installer and normal desktop launch

Tauri completed the corrected NSIS installer with exit code 0:
`app/windows/src-tauri/target/release/bundle/nsis/EXO Windows_0.3.70_x64-setup.exe`.
Size is 2,097,808,496 bytes (1.95 GiB), below the NSIS 2 GiB compressed-data limit.
SHA-256:
`20575cd3517453adab05d9f0ca4284a81ec7f696fc71d224aba3efe112749d49`.
Authenticode status is `NotSigned`; this is a review artifact, not a signed release.
The temporary build-only compression override selected zlib, without changing
production packaging configuration. Override SHA-256:
`eff5d7a06a0e58c15a1175f1a73a8a32f107745e188018cda12ad7f3b369c6e0`.
Receipt: `build/windows-runtime/review-package-receipt-417be.json`.

The desktop then started normally with development runtime/resource/dashboard,
offload/model-directory and Python-path environment overrides cleared. Its child
backend uses `target/release/runtime/exo.exe`; WebView2 uses the bundled
`target/release/resources/webview2`. The live capacity response again qualified
32B for RAM offload, 0.6B for VRAM, and rejected the 30B MoE entry. Offload is
enabled through the existing user's saved desktop settings, not package defaults.
Clean-machine installation, signing and publication remain pending. The earlier
superseded 1d installer ended with a file sharing error and is not successful
installer evidence.
