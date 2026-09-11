# A6 — `feat/model-card`

Compare: https://github.com/exo-explore/exo/compare/main...ovurrsl:exo:feat/model-card?expand=1

## Title

```
feat(models): add Qwen3-4B-4bit model card
```

## Description

```markdown
## Motivation

`resources/inference_model_cards/` carries Qwen3 cards at 30B, 8B and above, but
nothing in the 4B class. 4B at 4-bit is about 2.3 GB, which is the size that
actually fits on a single low-memory node and is the most useful thing to hand
someone trying exo for the first time — including on the Linux CPU path, where
anything larger is impractical.

## Changes

One new file, `resources/inference_model_cards/mlx-community--Qwen3-4B-4bit.toml`.
No code changes.

- Architecture fields (`n_layers = 36`, `hidden_size = 2560`,
  `num_key_value_heads = 8`, `context_length = 40960`) taken from the model's
  `config.json` on Hugging Face.
- `storage_size.in_bytes = 2278972183`, the summed size of the repository's
  weight files.
- `backends = ["MlxMetal", "MlxCuda", "MlxCpu"]` and `supports_tensor = true`,
  matching the sibling Qwen3 dense cards.
- `capabilities = ["text", "thinking", "thinking_toggle"]`, since Qwen3 4B has
  the same thinking-mode toggle as its siblings.
- Both `sampling_defaults` blocks are copied from Qwen's own "Best Practices"
  section, with the source URL kept as a comment above each, the same way the
  existing cards do it.

## Why It Works

Model cards are pure declarative metadata read by the card loader; adding one
registers a model without touching any code path. Every field used here already
appears in neighbouring Qwen3 cards, so there is no new schema surface.

## Test Plan

### Manual Testing
- Hardware: Ubuntu x86_64, Python 3.13 (no Apple Silicon available)
- Confirmed the TOML parses and that every field name it uses is present in the
  existing Qwen3 cards in the same directory.
- Cross-checked the architecture numbers against the model's `config.json` and
  the sampling defaults against the model card's Best Practices section.

I have not run inference with this card. There is no Apple Silicon on hand, and
the Linux CPU path is not currently usable (a separate issue I am writing up).
So this is a metadata contribution: the values are sourced and cross-checked,
but a generation run on real hardware would be worth doing before merge, and I
would rather say that than imply I did it.

### Automated Testing
No automated tests cover model card contents. The file is picked up by the
existing card loader with no registration step.
```
