import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  getWindowsCudaImageFitStatus,
  WINDOWS_SCHNELL_MINIMUM_GPU_BYTES,
  WINDOWS_SCHNELL_MODEL_ID,
} from "../src/lib/utils/windows-image-fit.ts";

const gib = 1024 ** 3;
const options = {
  minNodes: 1,
  instanceType: "MlxRing",
  nodeFilter: new Set(),
  modelStorageBytes: 15_470_210_592,
};
const node = (available = 8 * gib, total = 12 * gib) => ({
  os_version: "Windows 11",
  backends: ["MlxCuda"],
  macmon_info: { memory: { ram_total: total, ram_usage: total - available } },
});
const card = (backends = ["MlxMetal", "MlxCuda"], worldSize = 1) => [
  {
    DownloadPending: {
      shardMetadata: {
        PipelineShardMetadata: {
          worldSize,
          startLayer: 0,
          endLayer: 57,
          modelCard: { modelId: WINDOWS_SCHNELL_MODEL_ID, backends },
        },
      },
    },
  },
];
const fit = (nodes, downloads, extraOptions = {}) =>
  getWindowsCudaImageFitStatus(WINDOWS_SCHNELL_MODEL_ID, nodes, downloads, {
    ...options,
    ...extraOptions,
  });

test("a qualified single Windows GPU uses stage memory without subtracting reserve twice", () => {
  assert.equal(
    fit({ pc: node(WINDOWS_SCHNELL_MINIMUM_GPU_BYTES) }, { pc: card() }),
    "fits_now",
  );
  assert.equal(
    fit({ pc: node(WINDOWS_SCHNELL_MINIMUM_GPU_BYTES - 1) }, { pc: card() }),
    "fits_cluster_capacity",
  );
});
test("multiple small GPUs are never summed into one device fit", () => {
  assert.equal(
    fit(
      { a: node(4 * gib, 8 * gib), b: node(4 * gib, 8 * gib) },
      { a: card(), b: card() },
    ),
    "too_large",
  );
  assert.equal(
    fit({ a: node(), b: node() }, { a: card(), b: card() }, { minNodes: 2 }),
    "too_large",
  );
  assert.equal(
    fit({ a: node() }, { a: card() }, { instanceType: "MlxJaccl" }),
    "too_large",
  );
});
test("capacity fallback stays per device and subtracts the Windows reserve exactly once", () => {
  assert.equal(
    fit(
      { pc: node(0, WINDOWS_SCHNELL_MINIMUM_GPU_BYTES + 2.5 * gib) },
      { pc: card() },
    ),
    "fits_cluster_capacity",
  );
  assert.equal(
    fit(
      { pc: node(0, WINDOWS_SCHNELL_MINIMUM_GPU_BYTES + 2.5 * gib - 1) },
      { pc: card() },
    ),
    "too_large",
  );
});
test("pure Mac, Linux, unqualified cards and missing backend data retain the existing estimator", () => {
  for (const pc of [
    { ...node(), os_version: "15.3", backends: ["MlxMetal"] },
    { ...node(), os_version: "Linux" },
    { ...node(), backends: undefined },
  ])
    assert.equal(fit({ pc }, { pc: card() }), null);
  assert.equal(fit({ pc: node() }, { pc: card(["MlxMetal"]) }), null);
  assert.equal(fit({ pc: node() }, {}), null);
  assert.equal(fit({ pc: node() }, { pc: card(undefined, 2) }), null);
  assert.equal(
    getWindowsCudaImageFitStatus(
      "exolabs/FLUX.1-dev-4bit",
      { pc: node() },
      { pc: card() },
      options,
    ),
    null,
  );
});
test("filters exclude a capable device instead of borrowing its memory", () => {
  assert.equal(
    fit(
      { small: node(4 * gib, 8 * gib), large: node() },
      { small: card(), large: card() },
      { nodeFilter: new Set(["small"]) },
    ),
    "too_large",
  );
});
test("missing or malformed available memory cannot manufacture an immediate fit", () => {
  assert.equal(
    fit(
      {
        pc: {
          ...node(),
          macmon_info: undefined,
          system_info: { memory: 12 * gib },
        },
      },
      { pc: card() },
    ),
    "fits_cluster_capacity",
  );
  assert.equal(
    fit({ pc: node(Number.NaN) }, { pc: card() }),
    "fits_cluster_capacity",
  );
});
test("a busy Windows GPU does not hide a valid Mac placement in a mixed cluster", () => {
  const mac = {
    ...node(24 * gib, 32 * gib),
    os_version: "15.3",
    backends: ["MlxMetal"],
  };
  assert.equal(fit({ pc: node(0), mac }, { pc: card() }), "fits_now");
  assert.equal(
    fit({ pc: node(0), mac }, { pc: card() }, { instanceType: "MlxJaccl" }),
    "fits_now",
  );
  assert.equal(
    fit(
      {
        pc: node(4 * gib, 8 * gib),
        mac: {
          ...mac,
          macmon_info: { memory: { ram_total: 8 * gib, ram_usage: 4 * gib } },
        },
      },
      { pc: card() },
    ),
    "too_large",
  );
});
test("required node subsets cannot qualify a single CUDA device or borrow excluded transports", () => {
  const mac = {
    ...node(12 * gib, 16 * gib),
    os_version: "15.3",
    backends: ["MlxMetal"],
  };
  const nodes = { pc: node(), first: mac, second: mac };
  assert.equal(
    fit(nodes, { pc: card() }, { nodeFilter: new Set(["pc", "first"]) }),
    "too_large",
  );
  assert.equal(
    fit(
      nodes,
      { pc: card() },
      { minNodes: 2, nodeFilter: new Set(["first", "second"]) },
    ),
    "fits_now",
  );
  assert.equal(
    fit(
      nodes,
      { pc: card() },
      { minNodes: 3, nodeFilter: new Set(["first", "second"]) },
    ),
    "too_large",
  );
  assert.equal(
    fit(nodes, { pc: card() }, { nodeFilter: new Set(["unknown"]) }),
    "too_large",
  );
  assert.equal(
    fit(nodes, { pc: card() }, { nodeFilter: new Set(["pc"]) }),
    "fits_now",
  );
});
test("the dashboard budget agrees with the pinned Python stages while Mac storage remains unchanged", () => {
  const python = readFileSync(
    new URL(
      "../../src/exo/shared/models/windows_image_budget.py",
      import.meta.url,
    ),
    "utf8",
  );
  const layers = python.match(
    /layer_bytes=\(([\d_]+),\)\s*\*\s*(\d+)\s*\+\s*\(([\d_]+),\)\s*\*\s*(\d+)/,
  );
  assert.ok(layers);
  const bytes = (value) => Number(value.replaceAll("_", ""));
  const transformer =
    bytes(layers[1]) * Number(layers[2]) +
    bytes(layers[3]) * Number(layers[4]) +
    bytes(python.match(/replicated_transformer_bytes=([\d_]+)/)[1]);
  const prompt = bytes(python.match(/prompt_weight_bytes=([\d_]+)/)[1]);
  const vae = bytes(python.match(/vae_weight_bytes=([\d_]+)/)[1]);
  assert.equal(
    WINDOWS_SCHNELL_MINIMUM_GPU_BYTES,
    Math.max(transformer, prompt, vae),
  );
  const modelCard = readFileSync(
    new URL(
      "../../resources/image_model_cards/exolabs--FLUX.1-schnell-4bit.toml",
      import.meta.url,
    ),
    "utf8",
  );
  assert.match(modelCard, /\[storage_size\]\s+in_bytes = 15470210592/);
});
