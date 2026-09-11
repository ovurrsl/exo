/**
 * Infer the physical transport behind a topology edge so the dashboard can
 * label it accurately ("Thunderbolt 5", "Wi-Fi", etc.).
 *
 * Inputs we already have in state:
 *   - SocketConnection edges carry an IP, which appears in the sink node's
 *     `nodeNetwork.interfaces[].ipAddress` together with an `interfaceType`
 *     (wifi / ethernet / thunderbolt / unknown).
 *   - RDMAConnection edges carry interface names like "rdma_en3", which appear
 *     in `nodeThunderbolt[node].interfaces[].rdmaInterface` alongside a
 *     `linkSpeed` string from `system_profiler SPThunderboltDataType`
 *     (e.g. "Up to 40 Gb/s x1" → TB4, "Up to 80 Gb/s x1" → TB5).
 *
 * The output is a string label intended for direct display, plus the
 * structured pieces (kind + generation) so callers can do further styling.
 */

export type ConnectionKind =
  | "thunderbolt"
  | "ethernet"
  | "wifi"
  | "loopback"
  | "unknown";

export interface ConnectionType {
  /** Display label, e.g. "Thunderbolt 5 (RDMA)" or "Wi‑Fi". */
  label: string;
  /**
   * Very short form for drawing on the edge itself, e.g. "TB5" / "ETH" /
   * "Wi-Fi". Empty string when the kind is unknown, so the caller can render
   * nothing rather than a shrug. `label` stays the long form for tooltips.
   */
  badge: string;
  kind: ConnectionKind;
  /** "4" / "5" / undefined; only set for Thunderbolt. */
  thunderboltGeneration?: "3" | "4" | "5";
  /** True when the edge transports RDMA, false for plain TCP/IP. */
  isRdma: boolean;
  /** The matched linkSpeed string (e.g. "Up to 40 Gb/s x1"), if any. */
  linkSpeedHint?: string;
  /**
   * Link speed the sink interface has actually negotiated, in Mbps, from
   * `NetworkInterfaceInfo.active_speed_mbps`. Undefined when the OS does not
   * expose one - common for Wi-Fi, and for every interface on macOS.
   *
   * This is the nominal rate of the pipe, not measured throughput: the
   * profiler's upload/download figures say what the link is doing, these two
   * say what it could do. A node negotiated at 1 Gb on a 10 Gb card looks
   * fine in a throughput column and is obviously wrong beside its own
   * supported speed.
   */
  activeSpeedMbps?: number;
  /** Fastest speed the sink interface's hardware supports, in Mbps. */
  supportedSpeedMbps?: number;
}

interface RawNetworkInterface {
  name?: string;
  ipAddress?: string;
  addresses?: Array<{ address?: string } | string>;
  ipAddresses?: string[];
  ips?: string[];
  ipv4?: string;
  ipv6?: string;
  interfaceType?:
    | "wifi"
    | "ethernet"
    | "maybe_ethernet"
    | "thunderbolt"
    | "unknown";
  activeSpeedMbps?: number | null;
  supportedSpeedMbps?: number | null;
}

interface RawNodeNetwork {
  interfaces?: RawNetworkInterface[];
}

interface RawThunderboltIdent {
  rdmaInterface: string;
  domainUuid: string;
  linkSpeed: string;
}

interface RawNodeThunderbolt {
  interfaces: RawThunderboltIdent[];
}

export interface ConnectionTypeContext {
  nodeNetwork: Record<string, RawNodeNetwork>;
  nodeThunderbolt: Record<string, RawNodeThunderbolt>;
}

/** Parse a system_profiler "Up to N Gb/s xK" string into a TB generation. */
export function thunderboltGenerationFromLinkSpeed(
  linkSpeed: string | undefined,
): ConnectionType["thunderboltGeneration"] | undefined {
  if (!linkSpeed) return undefined;
  // Match the integer right before "Gb/s". Handles "Up to 40 Gb/s x1",
  // "40 Gb/s", "80 Gb/s", etc.
  const match = linkSpeed.match(/(\d+)\s*Gb\/s/i);
  if (!match) return undefined;
  const gbps = Number(match[1]);
  if (gbps >= 80) return "5";
  if (gbps >= 40) return "4";
  if (gbps >= 20) return "3";
  return undefined;
}

/** Short form drawn on the edge itself. Empty when there is nothing to say. */
function badgeFor(
  kind: ConnectionKind,
  thunderboltGeneration: ConnectionType["thunderboltGeneration"],
): string {
  switch (kind) {
    case "thunderbolt":
      return thunderboltGeneration ? `TB${thunderboltGeneration}` : "TB";
    case "ethernet":
      return "ETH";
    case "wifi":
      return "Wi-Fi";
    case "loopback":
      return "LO";
    case "unknown":
      return "";
  }
}

/**
 * A speed of 0 means "the OS did not tell us", not "this link is 0 Mbps" -
 * psutil reports 0 for an interface whose rate it cannot read. Fold that in
 * with null and absent so callers only ever see a real number or nothing.
 */
function positiveSpeed(value: number | null | undefined): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return undefined;
  }
  return value;
}

function findNetworkInterface(
  network: RawNodeNetwork | undefined,
  ip: string,
): RawNetworkInterface | undefined {
  if (!network?.interfaces) return undefined;
  for (const iface of network.interfaces) {
    if (iface.ipAddress === ip) return iface;
    if (iface.ipv4 === ip || iface.ipv6 === ip) return iface;
    if (iface.ipAddresses?.includes(ip)) return iface;
    if (iface.ips?.includes(ip)) return iface;
    if (
      iface.addresses?.some(
        (a) => (typeof a === "string" ? a : a?.address) === ip,
      )
    ) {
      return iface;
    }
  }
  return undefined;
}

function thunderboltIdentForIface(
  thunderbolt: RawNodeThunderbolt | undefined,
  rdmaInterface: string,
): RawThunderboltIdent | undefined {
  if (!thunderbolt?.interfaces) return undefined;
  return thunderbolt.interfaces.find((i) => i.rdmaInterface === rdmaInterface);
}

/** Connection type for an RDMA edge. */
export function inferRdmaConnectionType(
  sourceNodeId: string,
  edge: { sourceRdmaIface: string; sinkRdmaIface: string },
  context: ConnectionTypeContext,
): ConnectionType {
  // Both ends should report the same Thunderbolt generation; we read the
  // source side because it's our own node and most likely to be present.
  const ident = thunderboltIdentForIface(
    context.nodeThunderbolt[sourceNodeId],
    edge.sourceRdmaIface,
  );
  const generation = thunderboltGenerationFromLinkSpeed(ident?.linkSpeed);
  const label = generation
    ? `Thunderbolt ${generation} (RDMA)`
    : "Thunderbolt (RDMA)";
  return {
    label,
    badge: badgeFor("thunderbolt", generation),
    kind: "thunderbolt",
    thunderboltGeneration: generation,
    isRdma: true,
    linkSpeedHint: ident?.linkSpeed,
  };
}

// Sticky-cache keyed by (sinkNodeId, sinkIp). The backend re-derives
// nodeNetwork every 10 s from `networksetup`, and individual entries
// occasionally flicker (the IP is missing for one tick, then back). That
// would visibly bounce the label between "Ethernet" and "Unknown" between
// re-renders. Once we've classified a peer's IP as something concrete, we
// stick with that until we get a *different* concrete answer — transient
// "Unknown" readings are ignored.
const _socketTypeCache: Map<string, ConnectionType> = new Map();

/** Connection type for a SocketConnection edge identified by sink IP. */
export function inferSocketConnectionType(
  sinkNodeId: string,
  sinkIp: string,
  context: ConnectionTypeContext,
): ConnectionType {
  const fresh = _inferSocketConnectionTypeFresh(sinkNodeId, sinkIp, context);
  const cacheKey = `${sinkNodeId}|${sinkIp}`;
  if (fresh.kind !== "unknown") {
    _socketTypeCache.set(cacheKey, fresh);
    return fresh;
  }
  // Fresh classification couldn't determine a kind. Prefer the last good
  // answer over flickering to "Unknown".
  const cached = _socketTypeCache.get(cacheKey);
  if (cached && cached.kind !== "unknown") {
    return cached;
  }
  return fresh;
}

function _inferSocketConnectionTypeFresh(
  sinkNodeId: string,
  sinkIp: string,
  context: ConnectionTypeContext,
): ConnectionType {
  const iface = findNetworkInterface(context.nodeNetwork[sinkNodeId], sinkIp);
  const ifType = iface?.interfaceType;
  // Read from the interface the IP actually matched, so the speeds always
  // describe the link this edge runs over rather than the node's fastest NIC.
  const speeds = {
    activeSpeedMbps: positiveSpeed(iface?.activeSpeedMbps),
    supportedSpeedMbps: positiveSpeed(iface?.supportedSpeedMbps),
  };

  if (ifType === "thunderbolt") {
    // For TCP-over-Thunderbolt we don't have a direct linkSpeed mapping —
    // the rdmaInterface is named e.g. "rdma_en3" while the IP iface is "en3"
    // or a bridge. Best effort: scan the node's TB identifiers and pick the
    // fastest one; that's almost always the one carrying the connection.
    const tb = context.nodeThunderbolt[sinkNodeId];
    let bestGen: ConnectionType["thunderboltGeneration"] | undefined;
    let bestSpeed: string | undefined;
    for (const ident of tb?.interfaces ?? []) {
      const g = thunderboltGenerationFromLinkSpeed(ident.linkSpeed);
      if (g && (!bestGen || g > bestGen)) {
        bestGen = g;
        bestSpeed = ident.linkSpeed;
      }
    }
    return {
      label: bestGen ? `Thunderbolt ${bestGen} (TCP)` : "Thunderbolt (TCP)",
      badge: badgeFor("thunderbolt", bestGen),
      kind: "thunderbolt",
      thunderboltGeneration: bestGen,
      isRdma: false,
      linkSpeedHint: bestSpeed,
      ...speeds,
    };
  }

  if (ifType === "wifi") {
    return {
      label: "Wi‑Fi",
      badge: badgeFor("wifi", undefined),
      kind: "wifi",
      isRdma: false,
      ...speeds,
    };
  }
  if (ifType === "ethernet" || ifType === "maybe_ethernet") {
    return {
      label: "Ethernet",
      badge: badgeFor("ethernet", undefined),
      kind: "ethernet",
      isRdma: false,
      ...speeds,
    };
  }
  // Loopback IPs (Tailscale CGNAT 100.64.0.0/10, link-local, etc.) — surface
  // generically rather than guessing.
  return {
    label: "Unknown",
    badge: badgeFor("unknown", undefined),
    kind: "unknown",
    isRdma: false,
    ...speeds,
  };
}
