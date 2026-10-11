# Windows frozen 32B long-context deployment acceptance

The compilerless Windows runtime built from clean commit
`da6d72412592e47410d132ed74db470509a82f41` passed the real Qwen3-32B
acceptance and replaced the owned desktop runtime. Source validation remains
recorded separately in `windows-long-context-acceptance-20261011.md`.

## Frozen executable and gates

- Runtime SHA-256:
  `de5b9af52300146a46b5af3c7975a96c02f0c1c4da8a55cefad3c49e656db5a3`.
- Reviewed MLX `0.32.3.dev20261009+win.3` wheel and its pinned patch/provenance
  were checked before building. The build used the existing dashboard output.
- All **32 frozen CUDA/runtime gates passed**, including compilerless CPU/GPU,
  ring/process checks, and every tensor in the real **5,366,619,059-byte**
  `model-00001-of-00004.safetensors` shard. The large-file check was not skipped.
- The manifest records clean tracked source inputs. All **11,441 runtime files**
  matched their SHA-256 manifest in the build output and both desktop copies.

## Real frozen model acceptance

The isolated test used a unique namespace and ports, a separate `EXO_HOME`,
offline mode, and read-only existing model snapshots. It did not join the
normal desktop namespace. Before spawning, it checked that every model shard
existed and that tensor storage exceeded actual dedicated GPU capacity.
Model tensor storage was **18,429,667,328 bytes**, exceeding the measured
**12,820,938,752-byte** dedicated GPU capacity.
The harness checked executable SHA-256 against the manifest and recorded its
exact source commit, rather than using a source/dirty label.

- All six repeated Turkish fact requests returned `Kırmızı`, with automatic
  semantic and normal-finish assertions enabled.
- The long request used **8,122 prompt tokens** and returned
  `The color of the apple is **red**.` with a normal stop.
- Both streaming requests produced exactly **64 completion tokens**, a
  `length` finish, `[DONE]`, and matching server generation statistics/usage.
  Server generation rates were **0.947193** and **0.937753 tokens/s**.
- Cancellation recovered to a ready runner; the following request returned
  `Hello!` (the normalized `hello` assertion passed). The runner and node both
  exited normally with code **0**.
- Peak sampled owned process-tree RSS was **16,039,555,072 bytes**. Peak
  **system-wide** dedicated GPU use was **9,050,210,304 bytes**; it is not an
  attribution of that memory exclusively to EXO. Minimum system host available
  memory was **15,100,764,160 bytes**. Repeated-request observations are bounded
  samples, not proof of the absence of leaks.

Local evidence: `build/acceptance/qwen3-32b-long-context-frozen-da6d7241/`
contains `inference.json`, `node.log`, streaming statistics and memory samples.
`build/windows-runtime/build-da6d7241.log` records the frozen build and gates.

## Desktop deployment

Immediately before shutdown, the existing GUI/backend paths, child ownership,
API listener and empty instance map were checked. The owned backend's shutdown
event was retrieved and signaled; backend **28412 exited 0** before GUI **24116**
was stopped. Both previous runtime trees, the GUI, and all three firewall helper
copies were preserved in the unique workspace backup
`build/windows-runtime/backup-before-long-context-da6d7241-20261011-234229/`.

After full file validation, the helper and desktop were rebuilt with the new
runtime SHA-256 binding. That hash was found in all three helper copies and the
desktop executable. New GUI **12908** owns backend **15520** on **52415**;
the owned backend path and executable hash were checked. Discovery completed
before the live capacity assertion: Qwen3-32B reports `ram_offload`,
**6,854,230,016 bytes required**, **8,373,669,888 bytes available**, with no
active model instances. Available capacity is a live snapshot.

Desktop SHA-256:
`8f7d165a2113549a936148a0988623dc81ddc33367e9b4e9a07ff179f742019c`.
Deployment receipt:
`build/windows-runtime/normal-gui-long-context-da6d7241.json`;
log: `build/windows-runtime/deploy-da6d7241.log`.

This qualifies the tested Windows 32B/8K path on this machine. Approximately
one token/s is not the speed of a model fully resident in VRAM. Other model
architectures, signed installer release, clean consumer systems and a physical
Mac/Windows cluster were not qualified by this acceptance. No Mac source or
MLX patch/wheel pins changed during packaging/deployment.
