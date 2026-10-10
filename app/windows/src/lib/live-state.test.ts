import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { expect, it } from "vitest";
import { parseCluster } from "./cluster";

const path = process.env.EXO_DESKTOP_LIVE_STATE;
it.skipIf(!path)(
  "renders the actual frozen runtime state without inventing Windows system metrics",
  () => {
    const state = JSON.parse(readFileSync(path!, "utf8"));
    const cluster = parseCluster(state);
    expect(cluster.nodes).toHaveLength(1);
    const node = cluster.nodes[0];
    expect(node.id).toBe(state.topology.nodes[0]);
    expect(node.name).toBe(state.nodeIdentities[node.id].friendlyName);
    expect(node.total).toBeGreaterThan(0);
    expect(node.available).toBeGreaterThanOrEqual(0);
    expect(node.available).toBeLessThanOrEqual(node.total);
    if (!state.nodeSystem[node.id]) {
      expect(node.power).toBeNull();
      expect(node.gpu).toBeNull();
      expect(node.temperature).toBeNull();
    }
    writeFileSync(
      join(dirname(path!), "live-summary.json"),
      JSON.stringify(
        {
          nodes: cluster.nodes,
          edges: cluster.edges.length,
          instances: cluster.instances.length,
          downloads: cluster.downloads.length,
          tasks: cluster.tasks.length,
          totalComputeMemoryBytes: node.total,
          availableComputeMemoryBytes: node.available,
          missingMetricsRenderAs: "N/A",
        },
        null,
        2,
      ),
    );
  },
);
