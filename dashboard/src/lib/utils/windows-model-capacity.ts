export type ModelFitStatus =
  | "fits_now"
  | "fits_vram"
  | "ram_offload"
  | "fits_cluster_capacity"
  | "too_large";

export type WindowsModelCapacity = {
  mode: "vram" | "ram_offload" | "unavailable";
  required_bytes: number;
  available_bytes: number;
};
export type WindowsModelCapacities = Record<string, WindowsModelCapacity>;

type CapacityNode = { os_version?: string; backends?: string[] };
type CapacityOptions = {
  minNodes: number;
  instanceType: string;
  nodeFilter: ReadonlySet<string>;
};

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function parseWindowsModelCapacity(
  value: unknown,
): WindowsModelCapacities {
  const models = record(record(value)?.models);
  const capacities: WindowsModelCapacities = {};
  for (const [id, raw] of Object.entries(models ?? {})) {
    const item = record(raw);
    if (!item) continue;
    const { mode, required_bytes, available_bytes } = item;
    if (mode !== "vram" && mode !== "ram_offload" && mode !== "unavailable")
      continue;
    if (
      typeof required_bytes !== "number" ||
      !Number.isSafeInteger(required_bytes) ||
      required_bytes < 0
    )
      continue;
    if (
      typeof available_bytes !== "number" ||
      !Number.isSafeInteger(available_bytes) ||
      available_bytes < 0
    )
      continue;
    if (mode !== "unavailable" && required_bytes > available_bytes) continue;
    Object.defineProperty(capacities, id, {
      value: { mode, required_bytes, available_bytes },
      enumerable: true,
      configurable: true,
      writable: true,
    });
  }
  return capacities;
}

/** Older servers and temporary failures retain the existing memory estimator. */
export async function fetchWindowsModelCapacity(
  fetcher: typeof fetch = fetch,
): Promise<WindowsModelCapacities> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetcher("/windows/model-capacity", {
      signal: controller.signal,
    });
    return response.ok ? parseWindowsModelCapacity(await response.json()) : {};
  } catch {
    return {};
  } finally {
    clearTimeout(timeout);
  }
}

/** The private response describes this host, so never apply it to a cluster. */
export function getWindowsModelFitStatus(
  modelId: string,
  capacities: WindowsModelCapacities,
  nodes: Record<string, CapacityNode>,
  options: CapacityOptions,
): ModelFitStatus | null {
  const entries = Object.entries(nodes);
  if (entries.length !== 1) return null;
  const [id, node] = entries[0];
  if (
    !/^Windows(?:\s|$)/i.test(node.os_version ?? "") ||
    !node.backends?.includes("MlxCuda")
  )
    return null;
  if (
    options.minNodes !== 1 ||
    options.instanceType !== "MlxRing" ||
    options.nodeFilter.size > 1 ||
    (options.nodeFilter.size === 1 && !options.nodeFilter.has(id))
  )
    return null;
  const capacity = Object.hasOwn(capacities, modelId)
    ? capacities[modelId]
    : undefined;
  if (!capacity) return null;
  switch (capacity.mode) {
    case "vram":
      return "fits_vram";
    case "ram_offload":
      return "ram_offload";
    case "unavailable":
      return "too_large";
  }
}

export function isModelLoadable(status: ModelFitStatus): boolean {
  return (
    status === "fits_now" || status === "fits_vram" || status === "ram_offload"
  );
}

export function bestModelFitStatus(statuses: ModelFitStatus[]): ModelFitStatus {
  for (const status of [
    "fits_vram",
    "fits_now",
    "ram_offload",
    "fits_cluster_capacity",
  ] as const) {
    if (statuses.includes(status)) return status;
  }
  return "too_large";
}

export function getModelFitColor(status: ModelFitStatus): string {
  switch (status) {
    case "fits_now":
      return "text-white/40";
    case "fits_vram":
      return "text-green-400/80";
    case "ram_offload":
      return "text-exo-yellow/80";
    case "fits_cluster_capacity":
      return "text-orange-400/80";
    case "too_large":
      return "text-red-400/70";
  }
}
