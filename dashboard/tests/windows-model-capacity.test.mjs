import assert from "node:assert/strict";
import test from "node:test";
import {
  parseWindowsModelCapacity,
  fetchWindowsModelCapacity,
  getWindowsModelFitStatus,
  isModelLoadable,
  bestModelFitStatus,
  getModelFitColor,
} from "../src/lib/utils/windows-model-capacity.ts";

const nodes = { local: { os_version: "Windows 11", backends: ["MlxCuda"] } };
const options = { minNodes: 1, instanceType: "MlxRing", nodeFilter: new Set() };
const entry = (mode) => ({ mode, required_bytes: 100, available_bytes: 200 });

test("capacity modes preserve VRAM fit, qualify RAM loadability, and reject impossible models", () => {
  const capacity = parseWindowsModelCapacity({
    models: {
      small: entry("vram"),
      large: entry("ram_offload"),
      huge: entry("unavailable"),
    },
  });
  assert.equal(
    getWindowsModelFitStatus("small", capacity, nodes, options),
    "fits_vram",
  );
  assert.equal(
    getWindowsModelFitStatus("large", capacity, nodes, options),
    "ram_offload",
  );
  assert.equal(
    getWindowsModelFitStatus("huge", capacity, nodes, options),
    "too_large",
  );
  assert.equal(isModelLoadable("ram_offload"), true);
  assert.equal(isModelLoadable("fits_vram"), true);
  assert.equal(isModelLoadable("fits_now"), true);
  assert.equal(isModelLoadable("too_large"), false);
  assert.equal(isModelLoadable("fits_cluster_capacity"), false);
});

test("malformed, unsafe or contradictory capacities never qualify a model", () => {
  for (const value of [null, {}, { models: [] }, { models: null }])
    assert.deepEqual(parseWindowsModelCapacity(value), {});
  const models = {
    good: entry("ram_offload"),
    unknown: entry("other"),
    negative: { ...entry("ram_offload"), required_bytes: -1 },
    unsafe: {
      ...entry("ram_offload"),
      available_bytes: Number.MAX_SAFE_INTEGER + 1,
    },
    fraction: { ...entry("vram"), required_bytes: 0.5 },
    contradiction: { ...entry("vram"), required_bytes: 300 },
    null: null,
    unavailable: { ...entry("unavailable"), required_bytes: 300 },
  };
  assert.deepEqual(Object.keys(parseWindowsModelCapacity({ models })).sort(), [
    "good",
    "unavailable",
  ]);
});

test("private endpoint failure and old endpoint 404 fall back without errors", async () => {
  assert.deepEqual(
    await fetchWindowsModelCapacity(
      async () => new Response(null, { status: 404 }),
    ),
    {},
  );
  assert.deepEqual(
    await fetchWindowsModelCapacity(async () => {
      throw new Error("offline");
    }),
    {},
  );
  assert.deepEqual(
    await fetchWindowsModelCapacity(async () => new Response("bad json")),
    {},
  );
  let requested;
  const result = await fetchWindowsModelCapacity(async (url) => {
    requested = url;
    return Response.json({ models: { large: entry("ram_offload") } });
  });
  assert.equal(requested, "/windows/model-capacity");
  assert.deepEqual(result.large, entry("ram_offload"));
});

test("missing cards and Mac, mixed, unsupported placement filters retain legacy estimates", () => {
  const capacity = { large: entry("ram_offload") };
  assert.equal(
    getWindowsModelFitStatus("missing", capacity, nodes, options),
    null,
  );
  for (const topology of [
    {},
    { mac: { os_version: "macOS 15", backends: ["MlxMetal"] } },
    { ...nodes, mac: { os_version: "macOS 15", backends: ["MlxMetal"] } },
    { local: { os_version: "Windows 11", backends: ["MlxMetal"] } },
  ]) {
    assert.equal(
      getWindowsModelFitStatus("large", capacity, topology, options),
      null,
    );
  }
  for (const changed of [
    { minNodes: 2 },
    { instanceType: "MlxJaccl" },
    { nodeFilter: new Set(["other"]) },
    { nodeFilter: new Set(["local", "other"]) },
  ]) {
    assert.equal(
      getWindowsModelFitStatus("large", capacity, nodes, {
        ...options,
        ...changed,
      }),
      null,
    );
  }
  assert.equal(
    getWindowsModelFitStatus("large", capacity, nodes, {
      ...options,
      nodeFilter: new Set(["local"]),
    }),
    "ram_offload",
  );
});

test("group ranking prefers normal fit over offload and colors preserve Mac palette", () => {
  assert.equal(
    bestModelFitStatus(["too_large", "ram_offload", "fits_vram"]),
    "fits_vram",
  );
  assert.equal(
    bestModelFitStatus(["fits_cluster_capacity", "ram_offload"]),
    "ram_offload",
  );
  assert.equal(bestModelFitStatus([]), "too_large");
  assert.equal(getModelFitColor("fits_vram"), "text-green-400/80");
  assert.equal(getModelFitColor("ram_offload"), "text-exo-yellow/80");
  assert.equal(getModelFitColor("too_large"), "text-red-400/70");
  assert.equal(getModelFitColor("fits_now"), "text-white/40");
});
