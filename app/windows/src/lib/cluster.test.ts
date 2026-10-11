import { describe, expect, it } from "vitest";
import { parseCluster, validateEnvironment } from "./cluster";
describe("actual EXO API state contracts", () => {
  it("preserves tagged shard/download/task and heterogeneous node data", () => {
    const state = parseCluster({
      topology: {
        nodes: ["mac", "windows"],
        connections: {
          mac: { windows: [{ SocketConnection: { sinkMultiaddr: {} } }] },
        },
      },
      nodeIdentities: {
        mac: { friendlyName: "Mac Studio" },
        windows: { friendlyName: "CUDA PC" },
      },
      nodeMemory: {
        windows: {
          ramTotal: { inBytes: 16e9 },
          ramAvailable: { inBytes: 8e9 },
        },
      },
      nodeBackends: { windows: ["MlxCuda"] },
      instances: {
        instance: {
          MlxRingInstance: {
            shardAssignments: {
              modelId: "org/model",
              nodeToRunner: { windows: "runner" },
            },
          },
        },
      },
      runners: { runner: { RunnerReady: {} } },
      tasks: {
        task: {
          TextGeneration: {
            taskStatus: "Running",
            instanceId: "instance",
            taskParams: { messages: [{ content: "Hello" }] },
          },
        },
      },
      downloads: {
        windows: [
          {
            DownloadOngoing: {
              shardMetadata: {
                PipelineShardMetadata: { modelCard: { modelId: "org/model" } },
              },
              downloadProgress: {
                total: { inBytes: 1000 },
                downloaded: { inBytes: 500 },
                speed: 50,
                etaMs: 10000,
              },
            },
          },
        ],
      },
    });
    expect(state.instances[0].tasks[0].status).toBe("Running");
    expect(state.instances[0].status).toBe("Ready");
    expect(state.downloads[0].model).toBe("org/model");
    expect(state.downloads[0].downloaded).toBe(500);
    expect(state.nodes.find((node) => node.id === "windows")?.gpu).toBeNull();
    expect(state.edges).toHaveLength(1);
  });
  it("rejects case-insensitive collisions and invalid variables before saving", () => {
    expect(() =>
      validateEnvironment([
        { key: "custom_value", value: "a" },
        { key: "CUSTOM_VALUE", value: "b" },
      ]),
    ).toThrow("Duplicate");
    expect(() =>
      validateEnvironment([{ key: "INVALID KEY", value: "a" }]),
    ).toThrow("Invalid");
    expect(() =>
      validateEnvironment([{ key: "EXO_WINDOWS_SHUTDOWN_EVENT", value: "a" }]),
    ).toThrow("managed");
    expect(() => validateEnvironment([{ key: "Path", value: "a" }])).toThrow(
      "managed",
    );
    for (const key of [
      "HF_TOKEN",
      "hugging_face_hub_token",
      "HUGGINGFACE_HUB_TOKEN",
    ])
      expect(() => validateEnvironment([{ key, value: "secret" }])).toThrow(
        "Credential Manager",
      );
  });
});
