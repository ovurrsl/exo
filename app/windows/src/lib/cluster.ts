import type { Cluster, Download, JsonObject, Node, Task } from "./types";
export function object(value: unknown): JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : {};
}
export function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}
export function number(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
export function unwrap(value: unknown): { kind: string; value: JsonObject } {
  const raw = object(value);
  const entries = Object.entries(raw);
  return entries.length === 1 && typeof entries[0][1] === "object"
    ? { kind: entries[0][0], value: object(entries[0][1]) }
    : { kind: "", value: raw };
}
function bytes(value: unknown): number {
  const raw = object(value);
  return number(raw.inBytes ?? raw.in_bytes);
}
function metric(raw: JsonObject, key: string): number | null {
  return typeof raw[key] === "number" ? number(raw[key]) : null;
}
export function parseCluster(value: unknown): Cluster {
  const raw = object(value);
  const identities = object(raw.nodeIdentities);
  const memories = object(raw.nodeMemory);
  const systems = object(raw.nodeSystem);
  const capabilities = object(raw.nodeBackends);
  const topology = object(raw.topology);
  const ids = new Set([
    ...Object.keys(identities),
    ...Object.keys(memories),
    ...(Array.isArray(topology.nodes)
      ? topology.nodes.filter((n): n is string => typeof n === "string")
      : []),
  ]);
  const nodes: Node[] = [...ids].map((id) => {
    const identity = object(identities[id]);
    const memory = object(memories[id]);
    const system = object(systems[id]);
    return {
      id,
      name: text(identity.friendlyName, id.slice(0, 8)),
      chip: text(identity.chipId),
      os: text(identity.osVersion),
      total: bytes(memory.ramTotal),
      available: bytes(memory.ramAvailable),
      gpu: metric(system, "gpuUsage"),
      cpu: metric(system, "pcpuUsage"),
      temperature: metric(system, "temp"),
      power: metric(system, "sysPower"),
      backends: Array.isArray(capabilities[id])
        ? (capabilities[id] as unknown[]).filter(
            (x): x is string => typeof x === "string",
          )
        : [],
    };
  });
  const tasks: Task[] = Object.entries(object(raw.tasks)).map(([id, item]) => {
    const { kind, value } = unwrap(item);
    const params = object(value.taskParams);
    return {
      id,
      kind,
      status: text(value.taskStatus),
      prompt: JSON.stringify(params.messages ?? params.prompt ?? ""),
      error: text(value.errorMessage),
    };
  });
  const instances = Object.entries(object(raw.instances)).map(([id, item]) => {
    const { kind, value } = unwrap(item);
    const assignments = object(value.shardAssignments);
    const mapping = object(assignments.nodeToRunner);
    const runners = Object.values(mapping).filter(
      (x): x is string => typeof x === "string",
    );
    const statuses = runners.map((runner) =>
      unwrap(object(raw.runners)[runner]).kind.replace(/^Runner/, ""),
    );
    return {
      id,
      kind,
      model: text(assignments.modelId, "Unknown model"),
      nodes: Object.keys(mapping),
      runners,
      status: statuses.join(" · ") || "Pending",
      tasks: tasks.filter(
        (task) =>
          text(unwrap(object(raw.tasks)[task.id]).value.instanceId) === id,
      ),
    };
  });
  const edges: Cluster["edges"] = [];
  for (const [source, sinks] of Object.entries(object(topology.connections)))
    for (const [target, connections] of Object.entries(object(sinks))) {
      const list = Array.isArray(connections) ? connections : [];
      edges.push({
        source,
        target,
        rdma: list.some((edge) => "RDMAConnection" in object(edge)),
      });
    }
  const downloads: Download[] = Object.entries(object(raw.downloads)).flatMap(
    ([node, items]) =>
      (Array.isArray(items) ? items : []).map((item) => {
        const { kind, value } = unwrap(item);
        const progress = object(value.downloadProgress);
        const shard = value.shardMetadata;
        const card = object(unwrap(shard).value.modelCard);
        return {
          node,
          model: text(card.modelId),
          kind: kind.replace(/^Download/, ""),
          shard,
          downloaded: bytes(
            kind === "DownloadCompleted"
              ? value.total
              : (progress.downloaded ?? value.downloaded),
          ),
          total: bytes(progress.total ?? value.total),
          speed: number(progress.speed),
          eta: number(progress.etaMs),
          error: text(value.errorMessage),
          readOnly: value.readOnly === true,
        };
      }),
  );
  return { nodes, edges, instances, downloads, tasks };
}
export function formatBytes(value: number): string {
  if (value <= 0) return "0 B";
  const exponent = Math.min(4, Math.floor(Math.log(value) / Math.log(1024)));
  return `${(value / 1024 ** exponent).toFixed(exponent > 0 ? 1 : 0)} ${["B", "KiB", "MiB", "GiB", "TiB"][exponent]}`;
}
export function validateEnvironment(
  rows: { key: string; value: string }[],
): Record<string, string> {
  const result: Record<string, string> = {};
  const seen = new Set<string>();
  for (const row of rows) {
    const key = row.key.trim();
    if (!key && !row.value) continue;
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key))
      throw new Error(`Invalid environment variable: ${key}`);
    if (
      [
        "EXO_WINDOWS_SHUTDOWN_EVENT",
        "EXO_HOME",
        "EXO_RUNTIME_DIR",
        "PATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "EXO_API_PORT",
        "EXO_ZENOH_PORT",
        "EXO_DISCOVERY_PORT",
      ].includes(key.toUpperCase())
    )
      throw new Error(`${key} is managed by EXO.`);
    if (
      ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN"].includes(
        key.toUpperCase(),
      )
    )
      throw new Error(
        "Use the Hugging Face token field for Credential Manager.",
      );
    if (seen.has(key.toUpperCase()))
      throw new Error(`Duplicate environment variable: ${key}`);
    seen.add(key.toUpperCase());
    result[key] = row.value;
  }
  return result;
}
