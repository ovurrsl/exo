/** Single-device CUDA image fit; model storage and the Mac estimator stay separate. */
export const WINDOWS_SCHNELL_MODEL_ID = "exolabs/FLUX.1-schnell-4bit";
// Pinned full transformer payload from shared/models/windows_image_budget.py:
// 19 double blocks + 38 single blocks + replicated transformer parameters.
// This dominates the sequential prompt and VAE stages. NodeMemory.available
// already excludes the safety reserve, so subtract it only from total capacity.
export const WINDOWS_SCHNELL_MINIMUM_GPU_BYTES = 6_693_214_336;
const WINDOWS_CUDA_RESERVE_BYTES = 2_560 * 1024 * 1024;

type FitStatus = "fits_now" | "fits_cluster_capacity" | "too_large";
interface FitNode {
  os_version?: string;
  backends?: string[];
  system_info?: { memory?: number };
  macmon_info?: { memory?: { ram_total?: number; ram_usage?: number } };
}
interface FitOptions {
  minNodes: number;
  instanceType: string;
  nodeFilter: ReadonlySet<string>;
  modelStorageBytes: number;
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function hasQualifiedSingleNodeCard(entries: unknown[]): boolean {
  return entries.some((entry) => {
    const envelope = record(entry);
    if (!envelope || Object.keys(envelope).length !== 1) return false;
    const payload = record(Object.values(envelope)[0]);
    const shardEnvelope = record(
      payload?.shardMetadata ?? payload?.shard_metadata,
    );
    const shard = record(shardEnvelope?.PipelineShardMetadata);
    const card = record(shard?.modelCard ?? shard?.model_card);
    return (
      (card?.modelId ?? card?.model_id) === WINDOWS_SCHNELL_MODEL_ID &&
      Array.isArray(card?.backends) &&
      card.backends.includes("MlxCuda") &&
      (shard?.worldSize ?? shard?.world_size) === 1 &&
      (shard?.startLayer ?? shard?.start_layer) === 0 &&
      (shard?.endLayer ?? shard?.end_layer) === 57
    );
  });
}

/** null keeps the existing estimator, including every pure-Mac path. */
export function getWindowsCudaImageFitStatus(
  modelId: string,
  nodes: Record<string, FitNode>,
  downloads: Record<string, unknown[]>,
  options: FitOptions,
): FitStatus | null {
  if (modelId !== WINDOWS_SCHNELL_MODEL_ID) return null;
  const candidates = Object.entries(nodes).filter(
    ([id, node]) =>
      /^Windows(?:\s|$)/i.test(node.os_version ?? "") &&
      node.backends?.includes("MlxCuda") &&
      hasQualifiedSingleNodeCard(downloads[id] ?? []),
  );
  // A card advertises CUDA only after its Windows runtime is qualified. Older
  // Mac-only cards and missing backend/identity data do not activate this path.
  if (candidates.length === 0) return null;
  let hasSingleDeviceCapacity = false;
  for (const [id, node] of candidates) {
    // /instance/previews node_ids is a required subset, not an allowlist.
    if (
      options.minNodes !== 1 ||
      options.instanceType !== "MlxRing" ||
      options.nodeFilter.size > 1 ||
      (options.nodeFilter.size === 1 && !options.nodeFilter.has(id))
    )
      continue;
    const total =
      node.macmon_info?.memory?.ram_total ?? node.system_info?.memory ?? 0;
    const used = node.macmon_info?.memory?.ram_usage;
    if (!Number.isFinite(total) || total <= 0) continue;
    if (
      used !== undefined &&
      Number.isFinite(used) &&
      used >= 0 &&
      used <= total &&
      total - used >= WINDOWS_SCHNELL_MINIMUM_GPU_BYTES
    )
      return "fits_now";
    if (total - WINDOWS_CUDA_RESERVE_BYTES >= WINDOWS_SCHNELL_MINIMUM_GPU_BYTES)
      hasSingleDeviceCapacity = true;
  }
  // Keep valid Mac placements in mixed clusters using the original storage
  // estimate. Windows VRAM is never added to the Mac memory aggregate.
  const macNodes = Object.entries(nodes).filter(
    ([, node]) =>
      /^(?:\d|macOS(?:\s|$))/i.test(node.os_version ?? "") &&
      node.backends?.includes("MlxMetal"),
  );
  const macIds = new Set(macNodes.map(([id]) => id));
  if (
    ["MlxRing", "MlxJaccl"].includes(options.instanceType) &&
    macNodes.length >= Math.max(options.minNodes, options.nodeFilter.size) &&
    [...options.nodeFilter].every((id) => macIds.has(id)) &&
    Number.isFinite(options.modelStorageBytes) &&
    options.modelStorageBytes > 0
  ) {
    let totalMac = 0;
    let availableMac = 0;
    for (const [, node] of macNodes) {
      const total =
        node.macmon_info?.memory?.ram_total ?? node.system_info?.memory ?? 0;
      const used = node.macmon_info?.memory?.ram_usage;
      if (!Number.isFinite(total) || total <= 0) continue;
      totalMac += total;
      if (
        used !== undefined &&
        Number.isFinite(used) &&
        used >= 0 &&
        used <= total
      )
        availableMac += total - used;
    }
    if (availableMac >= options.modelStorageBytes) return "fits_now";
    if (totalMac >= options.modelStorageBytes) hasSingleDeviceCapacity = true;
  }
  return hasSingleDeviceCapacity ? "fits_cluster_capacity" : "too_large";
}
