export type InstanceStatusKind =
  | "failed"
  | "downloading"
  | "warming"
  | "running"
  | "ready"
  | "waiting"
  | "idle"
  | "preparing";
export function instanceStatus(
  status: string,
  hasActiveDownload = false,
): { kind: InstanceStatusKind; label: string } {
  // Same priority as the Mac InstanceViewModel; runner details remain intact.
  const value = status.toLowerCase();
  if (value.includes("failed")) return { kind: "failed", label: "Failed" };
  if (hasActiveDownload || value.includes("downloading"))
    return { kind: "downloading", label: "Downloading" };
  if (value.includes("warming"))
    return { kind: "warming", label: "Warming Up" };
  if (value.includes("running")) return { kind: "running", label: "Running" };
  if (value.includes("ready") || value.includes("loaded"))
    return { kind: "ready", label: "Ready" };
  if (value.includes("waiting")) return { kind: "waiting", label: "Waiting" };
  if (!value || value === "pending") return { kind: "idle", label: "Idle" };
  return { kind: "preparing", label: "Preparing" };
}
