import { expect, it } from "vitest";
import { instanceStatus } from "./presentation";
it("reduces many ranks and mixed states using the Mac priority", () => {
  expect(instanceStatus(Array(8).fill("Ready").join(" · "))).toEqual({
    kind: "ready",
    label: "Ready",
  });
  expect(instanceStatus("Ready · Running · Failed", true)).toEqual({
    kind: "failed",
    label: "Failed",
  });
  expect(instanceStatus("Ready · WarmingUp", true)).toEqual({
    kind: "downloading",
    label: "Downloading",
  });
  expect(instanceStatus("Running · WarmingUp")).toEqual({
    kind: "warming",
    label: "Warming Up",
  });
  expect(instanceStatus("Ready · Running")).toEqual({
    kind: "running",
    label: "Running",
  });
  expect(instanceStatus("Loaded · Waiting")).toEqual({
    kind: "ready",
    label: "Ready",
  });
  expect(instanceStatus("Connecting · Waiting")).toEqual({
    kind: "waiting",
    label: "Waiting",
  });
  expect(instanceStatus("Pending")).toEqual({ kind: "idle", label: "Idle" });
  expect(instanceStatus("Initializing")).toEqual({
    kind: "preparing",
    label: "Preparing",
  });
});
