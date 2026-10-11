import assert from "node:assert/strict";
import { after, test } from "node:test";
import {
  readFile,
  writeFile,
  mkdir,
  mkdtemp,
  unlink,
  rmdir,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { compile } from "svelte/compiler";
import { render } from "svelte/server";
import { isModelLoadable } from "../src/lib/utils/windows-model-capacity.ts";

const dashboard = fileURLToPath(new URL("../", import.meta.url));
const temporaryRoot = path.join(dashboard, ".svelte-kit");
await mkdir(temporaryRoot, { recursive: true });
const temporaryDirectory = await mkdtemp(
  path.join(temporaryRoot, "capacity-render-"),
);
const compiledPath = path.join(temporaryDirectory, "ModelPickerGroup.mjs");
after(async () => {
  await unlink(compiledPath);
  await rmdir(temporaryDirectory);
});
const source = await readFile(
  path.join(dashboard, "src/lib/components/ModelPickerGroup.svelte"),
  "utf8",
);
const compiled = compile(source, {
  filename: "ModelPickerGroup.svelte",
  generate: "server",
});
const utilityUrl = pathToFileURL(
  path.join(dashboard, "src/lib/utils/windows-model-capacity.ts"),
).href;
await writeFile(
  compiledPath,
  compiled.js.code.replace(
    /(["'])\$lib\/utils\/windows-model-capacity\1/g,
    JSON.stringify(utilityUrl),
  ),
);
const { default: ModelPickerGroup } = await import(
  pathToFileURL(compiledPath).href
);

function groupHtml(statuses, expanded = false) {
  const variants = Object.keys(statuses).map((id) => ({
    id,
    name: id,
    storage_size_megabytes: 18000,
    quantization: "4bit",
  }));
  return render(ModelPickerGroup, {
    props: {
      group: {
        id: "qwen",
        name: "Qwen3",
        family: "qwen",
        capabilities: ["text"],
        variants,
        smallestVariant: variants[0],
        hasMultipleVariants: variants.length > 1,
      },
      isExpanded: expanded,
      isFavorite: false,
      selectedModelId: null,
      getModelFitStatus: (id) => statuses[id],
      canModelFit: (id) => isModelLoadable(statuses[id]),
      onToggleExpand: () => {},
      onSelectModel: () => {},
      onToggleFavorite: () => {},
      onShowInfo: () => {},
    },
  }).body;
}

test("qualified RAM model renders explicit yellow offload label and system RAM explanation", () => {
  const html = groupHtml({ large: "ram_offload" });
  assert.match(html, /text-exo-yellow\/80/);
  assert.match(html, /RAM offload/);
  assert.match(
    html,
    /Weights use system RAM; decoder layers are staged in VRAM/,
  );
  assert.doesNotMatch(html, /opacity-40/);
});

test("normal Windows fit renders green and impossible fit renders red", () => {
  assert.match(groupHtml({ small: "fits_vram" }), /text-green-400\/80/);
  assert.match(groupHtml({ huge: "too_large" }), /text-red-400\/70/);
  assert.doesNotMatch(groupHtml({ huge: "too_large" }), /RAM offload/);
});

test("Mac fit retains existing neutral size color and no offload label", () => {
  const html = groupHtml({ mac: "fits_now" });
  assert.match(html, /text-white\/40/);
  assert.doesNotMatch(html, /RAM offload/);
  assert.doesNotMatch(html, /text-green-400\/80/);
});

test("expanded variants retain per-model labels when the group also has a normal VRAM fit", () => {
  const html = groupHtml(
    { small: "fits_vram", large: "ram_offload", huge: "too_large" },
    true,
  );
  assert.match(html, /text-green-400\/80/);
  assert.match(html, /text-exo-yellow\/80/);
  assert.match(html, /text-red-400\/70/);
  assert.match(html, /RAM offload/);
});
