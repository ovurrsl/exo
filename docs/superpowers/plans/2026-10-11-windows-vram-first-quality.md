# Windows VRAM First and Output Accuracy Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task by task. Verify each change before committing.

**Goal:** Correct Windows offload output logits, then keep the largest safe weight set in dedicated VRAM and retain only overflow weights in RAM.

**Architecture:** First fix the proven BF16 CPU projection error without changing canonical quantized weights or ordinary CUDA/Mac loading. Separately implement deterministic VRAM residency from actual NVML capacity, bounded KV/workspace/copy reserves and explicit GPU streams. Use the existing opt-in dense Qwen3 boundary; do not expand architecture support.

**Tech Stack:** Python 3.13, pinned MLX CUDA, mlx-lm Qwen3, NVML, pytest, existing EXO HTTP acceptance tools.

**Spec:** [Research and requirements](../../windows-vram-first-quality-research-20261010.md).

## Global Constraints

- Default API port 52415; isolated acceptance may choose a temporary private port.
- No Swift/Metal/JACCL or Darwin dependency-pin changes; no shared event/state JSON additions.
- Single Windows CUDA node, dense built-in Qwen3, affine 4-bit group32/group64, batch one, opt-in only.
- Canonical packed U32 weights and BF16 storage stay intact; remote snapshot Python stays prohibited.
- Preserve lazy discarded prefill logits, synchronization, bounded context and cancellation cleanup.
- Topic branch `work/windows-vram-first-quality`; independent verified commits, push own fork and merge into windows-native.
- Physical Mac clustering and Thunderbolt remain deferred. Unsigned installer is a review artifact, not a release.

## Review Focus

1. Large BF16 hidden width can produce finite but incorrect logits: compare against independent FP32 reference.
2. Tied embedding/head projection must receive the same accuracy fix without changing token lookup.
3. Another app can consume VRAM after selection: recheck during initialization/staging, controlled failure rather than host-capacity substitution.
4. Resident CPU copies, aliases or lazy graphs can retain all host weights: validate ownership and measured host peak.
5. Chat settings, cache and cancellation can hide numerical errors: fresh sampled Turkish and multi-turn tests, separate from greedy diagnostics.

## Task 1: Accurate Windows CPU output projection

**Files:** `src/exo/worker/engines/mlx/windows_text_offload.py`; `src/exo/worker/tests/unittests/test_mlx/test_windows_text_offload.py` or a focused companion numerical test.

**Interfaces:** existing `prepare_windows_qwen3_offload(...) -> WindowsQwen3OffloadModel` and `__call__(inputs, cache, input_embeddings) -> mx.array` stay unchanged. An internal projection adapter may wrap QuantizedLinear/QuantizedEmbedding while preserving canonical parameter storage and tied lookup behavior.

- [x] Write a regression with BF16 quantized head width 5120 and independently dequantized FP32 reference; cover tied/untied, prefill/decode and unchanged canonical dtype/storage.
- [x] Run against current source and record failure due to numerical drift, not missing imports or mocks.
- [x] Promote activation/scales/affine biases to FP32 at the CPU projection operation; leave packed weights intact and avoid eager vocabulary projection of discarded prefill.
- [x] Pass numerical regression, existing offload cleanup/KV/parity tests, Windows/Darwin strict types, Ruff and default pytest suite.
- [x] Commit focused code and tests; report numerical proof without claiming full chat acceptance.

Record: `a567c59b`; default suite 802 passed/8 skipped/195 deselected, one expected malicious-tokenizer fallback warning; strict Windows/Darwin types and Ruff clean. Real sampled nonthinking Turkish greeting, arithmetic, color and multi-turn name recall all stopped normally. Thinking-on 128-token probe truncated inside reasoning; a trailing fragment was mislabeled final content. Cancellation/recovery passed, semantic thinking final acceptance remains open.

## Task 2: Real sampled chat acceptance

**Files:** `scripts/windows/check_inference.py` (only if a reusable quality mode is warranted), acceptance records under ignored `build/acceptance`, research/capacity reports.

**Interfaces:** existing isolated-node HTTP tool; requests use explicit model, temperature/top-p/top-k/min-p/seed/thinking parameters. Never attach to or cancel the user's active model.

- [ ] Preflight user instance list empty and available host/GPU capacity; run exact topic source using source/runtime origins recorded in report.
- [ ] Test new Turkish greeting (`Naber?`), explicit Turkish instructions, arithmetic and multi-turn context at nonthinking 0.7/0.8/20/0, plus bounded thinking-on 0.6/0.95/20/0. Record raw content/reasoning, tokens, TTFT/decode and finish reason.
- [ ] Reject empty or repeated-digit output; inspect meaning manually as well as machine invariants. Thinking traces must not be mislabeled final answers.
- [ ] Test cancellation/recovery and clean owned-process shutdown. Do not interpret max-token truncation as successful complete reasoning.
- [ ] Commit acceptance scope/remaining limitations separately. If wrong replies persist, trace final norm, decoder logits/KV and tokenizer state before residency work.

## Task 3: VRAM resident weight plan and overflow-only ownership

**Files:** new `src/exo/utils/windows_residency.py` and tests; `windows_text_offload.py`; only necessary capacity/admission integration in existing Windows modules.

**Interfaces:** immutable internal plan consuming actual free dedicated bytes, exact component byte sizes and policy. Output resident component IDs, overflow component IDs, persistent bytes and transient/reserve budgets; do not expose it through shared strict messages.

- [ ] Define independent literal-budget tests for exact fit, no space, changed capacity, tied alias accounting and KV growth. The sum must include resident weights, one staged layer, copy temporaries, context KV and workspace.
- [ ] Write GPU tests that prove resident layers are not copied per token and execute on GPU streams; overflow layers preserve existing sync/restore lifecycle.
- [ ] Cold-load component by component. Materialize resident device tensors, synchronize and release host references; retain canonical host trees only for overflow. Prioritize GPU head/norm, then safe decoder residency; embedding placement respects alias ownership.
- [ ] On initialization/copy failure release only owned device refs after synchronization and fail/replan before serving; no silent all-CPU success. Staging checks remaining actual free VRAM without counting resident weights twice.
- [ ] Make capacity/loader share conservative qualification; retain green/yellow/red labels and Mac layout.
- [ ] Verify ordinary VRAM fit path and Mac/Darwin regressions, host ownership after preparation, partial-failure cleanup and VRAM pressure behavior; commit residency separately from accuracy.

## Task 4: Performance and packaged acceptance

**Files:** acceptance scripts/receipts, capacity and progress documentation; existing Windows frozen/runtime packaging only.

- [ ] Same pinned 32B snapshot/input/seed/context: record dedicated GPU peak (global vs owned distinguished), owned RSS, available host, prefill/decode/TTFT and transfer/projection costs.
- [ ] Demonstrate dedicated VRAM residency and lower host weight retention; compare with approximately 0.11 token/s baseline without promising hardware-independent speed.
- [ ] Run repeated chat/context/cache/abort/restart and ordinary small GPU model acceptance; default pytest, strict Windows/Darwin types and Ruff.
- [ ] Freeze exact verified source, rerun frozen gates and sampled oversized-model acceptance; normal desktop still 52415.
- [ ] Check installer size, exact hashes/source receipts, signatures and clean-install limitations. Do not publish until required release gates pass.
- [ ] Review immutable diff, commit/push own fork and merge verified increments to windows-native.

## Self-review

Accuracy is an independent shippable fix. Residency starts only after sampled chat diagnosis, so a faster corrupt model is never accepted. Task Manager shared usage is global and may include driver backing; success means measured placement and ownership, not a promise of zero shared memory. Historical acceptance reports are retained with explicit qualification limits.
