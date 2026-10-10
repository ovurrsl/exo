# Windows model capacity and experimental RAM offload

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
Offload is not enabled by default while acceptance on an actual >12 GB model is
pending. Thus the yellow label is a qualified experimental mode, not a claim that
every model fitting physical RAM is supported or that performance equals VRAM.

## Verification and remaining work

- Python regression: 777 passed, 8 skipped, 191 deselected. After review, the
  loader was changed to strict loading and all five loader tests passed, including
  real missing-file and missing-tensor cases.
- Full Windows and Darwin Python type checks: zero errors before the final strict
  loader change; targeted checks of that change also passed. Ruff check and format
  check passed. Nix is unavailable on this Windows machine.
- Small real CUDA staging/logit/KV parity and failure cleanup were previously
  exercised. This does not substitute for a model larger than dedicated VRAM.
- Dashboard production build passed. Svelte check has the same 15 errors and six
  warnings as the unchanged baseline; no new diagnostics were introduced.
- All 18 dashboard capacity/image-fit/render tests passed, including actual Svelte
  picker markup for green VRAM fit, yellow RAM offload, red insufficient capacity,
  and individual labels in expanded multi-variant groups. Prettier check passed.
- `mlx-community/Qwen3-32B-4bit` revision
  `bcaaf7f538adf166c1080a2befdb4f6019f66639` was selected for large-model acceptance
  (18,429,667,328 tensor bytes). Download and actual large-model acceptance remain
  pending. Do not claim production RAM offload acceptance from unit tests.
- The running frozen Windows application still contains the older runtime.
  Rebuilding and replacing the installed runtime is a separate pending step.
- Mac clustering remains deferred as requested. No Mac Swift files were changed.
