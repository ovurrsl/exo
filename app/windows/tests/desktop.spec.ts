import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
const liveStatePath = process.env.EXO_DESKTOP_LIVE_STATE;
const settings = {
  schemaVersion: 1,
  namespace: "",
  hfEndpoint: "",
  offline: false,
  enableImageModels: false,
  fastSynch: true,
  startOnLogin: true,
  defaultModelsDirectory: "",
  additionalModelsDirectories: [],
  readOnlyModelsDirectories: [],
  customEnvironment: {},
  onboardingCompleted: true,
};
test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    ({ settings }) => {
      let status = "Running";
      const calls: { command: string; args: Record<string, unknown> }[] = [];
      Object.assign(window, {
        __EXO_CALLS__: calls,
        __EXO_TEST_BRIDGE__: async (
          command: string,
          args: Record<string, unknown>,
        ) => {
          calls.push({ command, args });
          if (command === "snapshot")
            return {
              status:
                (window as unknown as { __EXO_STATUS_OVERRIDE__?: string })
                  .__EXO_STATUS_OVERRIDE__ ?? status,
              detail: "",
              owned:
                ((window as unknown as { __EXO_STATUS_OVERRIDE__?: string })
                  .__EXO_STATUS_OVERRIDE__ ?? status) === "Running",
              nodeId:
                (window as unknown as { __EXO_NODE_OVERRIDE__?: string })
                  .__EXO_NODE_OVERRIDE__ ?? "windows",
              version: "0.3.70",
              sourceCommit: "931e0ff4a4fcdb0a5f04f7a71f3a5e4201867df3",
              sourceModified: true,
              mlxVersion: "0.32.3.dev20261009+win.3",
              runtimePath: "C:\\EXO\\runtime",
              dataPath: "C:\\Data\\exo",
              logPath: "C:\\Data\\exo\\exo_log",
              update: null,
              updaterConfigured: false,
            };
          if (command === "get_settings")
            return { settings, hfTokenPresent: true };
          if (command === "save_settings")
            return { settings: args.settings, hfTokenPresent: true };
          if (command === "stop_backend") status = "Stopped";
          if (command === "start_backend") status = "Running";
          if (command === "pick_directory") return "D:\\Shared models";
          if (command === "cluster_state")
            return (
              (window as unknown as { __EXO_STATE_OVERRIDE__?: unknown })
                .__EXO_STATE_OVERRIDE__ ?? {
                topology: {
                  nodes: ["windows", "mac"],
                  connections: { mac: { windows: [{ SocketConnection: {} }] } },
                },
                nodeIdentities: {
                  windows: { friendlyName: "CUDA PC", chipId: "RTX 5090" },
                  mac: { friendlyName: "Mac Studio", chipId: "M4 Max" },
                },
                nodeMemory: {
                  windows: {
                    ramTotal: { inBytes: 32 * 1024 ** 3 },
                    ramAvailable: { inBytes: 20 * 1024 ** 3 },
                  },
                },
                instances: {
                  first: {
                    MlxRingInstance: {
                      shardAssignments: {
                        modelId: "org/Qwen3",
                        nodeToRunner: { windows: "runner", mac: "other" },
                      },
                    },
                  },
                },
                runners: { runner: { RunnerReady: {} } },
                tasks: {
                  task: {
                    TextGeneration: {
                      instanceId: "first",
                      taskStatus: "Running",
                      taskParams: { messages: [{ content: "Hello" }] },
                    },
                  },
                },
              }
            );
          return null;
        },
      });
    },
    { settings },
  );
});
async function expectTrayControlsWithinViewport(page: Page) {
  expect(
    await page.evaluate(() => document.documentElement.scrollHeight),
  ).toBeLessThanOrEqual(page.viewportSize()!.height);
  for (const name of ["Settings…", "Quit"]) {
    const control = page.getByRole("button", { name, exact: true });
    const bounds = await control.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.y).toBeGreaterThanOrEqual(0);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(
      page.viewportSize()!.height,
    );
  }
  await page.getByRole("checkbox", { name: "Run EXO" }).focus();
  const visited = new Set<string>();
  for (let index = 0; index < 30; index++) {
    await page.keyboard.press("Tab");
    for (const name of ["Settings…", "Quit"]) {
      if (
        await page
          .getByRole("button", { name, exact: true })
          .evaluate((element) => element === document.activeElement)
      )
        visited.add(name);
    }
  }
  expect([...visited].sort()).toEqual(["Quit", "Settings…"]);
}
for (const height of [650, 440]) {
  test(`tray controls stay reachable with a long error at ${height}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 340, height });
    await page.goto("/");
    await page.evaluate(() => {
      const desktopWindow = window as unknown as {
        __EXO_TEST_BRIDGE__: (
          command: string,
          args: Record<string, unknown>,
        ) => Promise<unknown>;
      };
      const bridge = desktopWindow.__EXO_TEST_BRIDGE__;
      desktopWindow.__EXO_TEST_BRIDGE__ = (command, args) =>
        command === "check_update"
          ? Promise.reject(
              "Backend could not complete the request. ".repeat(80),
            )
          : bridge(command, args);
    });
    await page
      .getByRole("button", { name: "Check for Updates", exact: true })
      .click();
    await expect(page.getByRole("alert")).toContainText(
      "Backend could not complete",
    );
    await expectTrayControlsWithinViewport(page);
    await page.screenshot({
      path: test.info().outputPath("tray-long-error.png"),
    });
    await page.getByRole("button", { name: "Dismiss error" }).click();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expectTrayControlsWithinViewport(page);
  });
}
test("tray controls stay reachable while the API copy notice is shown", async ({
  page,
}) => {
  await page.setViewportSize({ width: 340, height: 650 });
  await page.goto("/");
  await page.getByRole("button", { name: "Copy API URL" }).click();
  await expect(page.getByRole("status")).toContainText("API URL copied");
  await expectTrayControlsWithinViewport(page);
  await page.screenshot({
    path: test.info().outputPath("tray-copy-notice.png"),
  });
});
test("unchanged or reverted active settings cannot be saved and About has no save", async ({
  page,
}) => {
  await page.goto("/?view=settings");
  const save = page.getByRole("button", { name: "Save & Restart" });
  await expect(save).toBeDisabled();
  await page.getByLabel("Cluster namespace").fill("changed");
  await expect(save).toBeEnabled();
  await page.getByLabel("Cluster namespace").fill("");
  await expect(save).toBeDisabled();
  await page.getByLabel("Hugging Face token").fill("   ");
  await expect(save).toBeDisabled();
  await page.getByRole("checkbox", { name: "Remove saved token" }).check();
  await expect(save).toBeEnabled();
  await page.getByRole("checkbox", { name: "Remove saved token" }).uncheck();
  await expect(save).toBeDisabled();
  await page.getByRole("button", { name: "Model", exact: true }).click();
  await expect(save).toBeDisabled();
  await page.getByRole("checkbox", { name: "Enable image models" }).check();
  await expect(save).toBeEnabled();
  await page.getByRole("checkbox", { name: "Enable image models" }).uncheck();
  await expect(save).toBeDisabled();
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  await expect(save).toBeDisabled();
  await page.getByRole("checkbox", { name: "Fast synchronization" }).uncheck();
  await expect(save).toBeEnabled();
  await page.getByRole("checkbox", { name: "Fast synchronization" }).check();
  await expect(save).toBeDisabled();
  await page.getByRole("button", { name: "Environment", exact: true }).click();
  await expect(save).toBeDisabled();
  await page.getByRole("button", { name: "Add Variable", exact: true }).click();
  await expect(save).toBeDisabled();
  await page.getByLabel("Variable name").fill("EXO_OFFLINE");
  await expect(save).toBeEnabled();
  await page.getByLabel("Variable name").fill("");
  await expect(save).toBeDisabled();
  await page.getByRole("button", { name: "About", exact: true }).click();
  await expect(save).toHaveCount(0);
});
test("saving one settings tab preserves other drafts and submits only its fields", async ({
  page,
}) => {
  await page.goto("/?view=settings");
  await page.getByLabel("Cluster namespace").fill("general-draft");
  await page.getByLabel("Hugging Face token").fill("secret-draft");
  await page.getByRole("button", { name: "Environment", exact: true }).click();
  await page.getByRole("button", { name: "Add Variable", exact: true }).click();
  await page.getByLabel("Variable name").fill("Path");
  await page.getByLabel("Variable value").fill("C:\\invalid-runtime");
  await page.getByRole("button", { name: "Model", exact: true }).click();
  await page.getByRole("checkbox", { name: "Enable image models" }).check();
  await page.getByRole("button", { name: "Save & Restart" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText("Model");
  const modelSave = await page.evaluate(
    () =>
      (
        window as unknown as {
          __EXO_CALLS__: { command: string; args: Record<string, unknown> }[];
        }
      ).__EXO_CALLS__.find((call) => call.command === "save_settings")?.args,
  );
  expect(modelSave).toMatchObject({
    settings: { namespace: "", enableImageModels: true, customEnvironment: {} },
    hfToken: null,
    clearHfToken: false,
  });
  await expect(
    page.getByRole("button", { name: "Save & Restart" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "General", exact: true }).click();
  await expect(page.getByLabel("Cluster namespace")).toHaveValue(
    "general-draft",
  );
  await expect(page.getByLabel("Hugging Face token")).toHaveValue(
    "secret-draft",
  );
  await expect(
    page.getByRole("button", { name: "Save & Restart" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Save & Restart" }).click();
  await expect(page.getByRole("status")).toContainText("General");
  await page.getByRole("button", { name: "Environment", exact: true }).click();
  await expect(page.getByLabel("Variable name")).toHaveValue("Path");
  await page.getByRole("button", { name: "Save & Restart" }).click();
  await expect(page.getByRole("alert")).toContainText("Path is managed by EXO");
});
test("stopped settings save copy does not promise a backend restart", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.assign(window, { __EXO_STATUS_OVERRIDE__: "Stopped" }),
  );
  await page.goto("/?view=settings");
  await page.getByLabel("Cluster namespace").fill("next-launch");
  await expect(page.locator(".settings-footer")).toContainText(
    "next backend launch",
  );
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("next backend launch");
  await expect(page.getByRole("status")).not.toContainText("restarted");
});
test("running token save does not claim a restart the response cannot confirm", async ({
  page,
}) => {
  await page.goto("/?view=settings");
  await page.getByLabel("Hugging Face token").fill("hf-already-saved");
  await page.getByRole("button", { name: "Save & Restart" }).click();
  await expect(page.getByRole("status")).toContainText(
    "General settings saved",
  );
  await expect(page.getByRole("status")).not.toContainText("restarted");
});
for (const invalidToken of ["\thf-secret\t", "\n"]) {
  test(`General submits token controls unchanged for backend rejection: ${JSON.stringify(invalidToken)}`, async ({
    page,
  }) => {
    await page.goto("/?view=settings");
    await page.evaluate(() => {
      const desktopWindow = window as unknown as {
        __EXO_TEST_BRIDGE__: (
          command: string,
          args: Record<string, unknown>,
        ) => Promise<unknown>;
      };
      const bridge = desktopWindow.__EXO_TEST_BRIDGE__;
      desktopWindow.__EXO_TEST_BRIDGE__ = async (command, args) => {
        const result = await bridge(command, args);
        if (
          command === "save_settings" &&
          typeof args.hfToken === "string" &&
          /[\u0000-\u001f\u007f]/.test(args.hfToken)
        )
          throw new Error("The token contains invalid control characters.");
        return result;
      };
    });
    await page.getByLabel("Cluster namespace").fill("token-validation");
    await page.getByLabel("Hugging Face token").fill(invalidToken);
    // A single-line input strips literal line feeds. Simulate an untrusted
    // programmatic value at the event boundary to keep this regression explicit.
    if (invalidToken === "\n") {
      await page.getByLabel("Hugging Face token").evaluate((element) => {
        Object.defineProperty(element, "value", {
          value: "\n",
          configurable: true,
        });
        element.dispatchEvent(new Event("input", { bubbles: true }));
      });
    }
    await page.getByRole("button", { name: "Save & Restart" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "invalid control characters",
    );
    const submitted = await page.evaluate(
      () =>
        (
          window as unknown as {
            __EXO_CALLS__: { command: string; args: Record<string, unknown> }[];
          }
        ).__EXO_CALLS__.find((call) => call.command === "save_settings")?.args,
    );
    expect(submitted?.hfToken).toBe(invalidToken);
    await expect(
      page.getByRole("button", { name: "Save & Restart" }),
    ).toBeEnabled();
  });
}
test("About identifies the runtime source and native MLX build", async ({
  page,
}) => {
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "About", exact: true }).click();
  await expect(
    page.getByText("931e0ff4a4fcdb0a5f04f7a71f3a5e4201867df3", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.getByText("Working tree changes included.")).toBeVisible();
  await expect(
    page.getByText("0.32.3.dev20261009+win.3", { exact: true }),
  ).toBeVisible();
});

test("tray shows real cluster data and opens the existing dashboard", async ({
  page,
}) => {
  await page.setViewportSize({ width: 340, height: 650 });
  await page.goto("/");
  await page.getByRole("button", { name: "Show nodes", exact: true }).click();
  await page
    .getByRole("button", { name: "Show instances", exact: true })
    .click();
  await expect(page.getByText("CUDA PC").last()).toBeVisible();
  await expect(page.getByText("Qwen3")).toBeVisible();
  await page.getByRole("button", { name: "Web Dashboard" }).click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        (
          window as unknown as { __EXO_CALLS__: { command: string }[] }
        ).__EXO_CALLS__.some((call) => call.command === "open_dashboard"),
      ),
    )
    .toBe(true);
  await page.screenshot({ path: "test-results/tray.png", fullPage: true });
  await page.getByRole("checkbox", { name: "Run EXO" }).uncheck();
  await expect(
    page.getByRole("checkbox", { name: "Run EXO" }),
  ).not.toBeChecked();
  await expect(page.getByRole("button", { name: "Web Dashboard" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("img", { name: "Cluster network topology" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Settings…" })).toBeVisible();
});
test("five settings tabs persist namespace, secure token input and model directories", async ({
  page,
}) => {
  await page.setViewportSize({ width: 640, height: 560 });
  await page.goto("/?view=settings");
  for (const name of ["General", "Model", "Advanced", "Environment", "About"])
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  await page.getByLabel("Cluster namespace").fill("shared-cluster");
  await page.getByLabel("Hugging Face token").fill("test-secret");
  await page.getByRole("button", { name: "Save & Restart" }).click();
  await page.getByRole("button", { name: "Environment", exact: true }).click();
  await page.getByRole("button", { name: "Add Read-only Directory" }).click();
  await page.getByRole("button", { name: "Save & Restart" }).click();
  const saved = await page.evaluate(
    () =>
      (
        window as unknown as {
          __EXO_CALLS__: { command: string; args: Record<string, unknown> }[];
        }
      ).__EXO_CALLS__
        .filter((call) => call.command === "save_settings")
        .at(-1)?.args,
  );
  expect(saved?.hfToken).toBeNull();
  expect(saved?.settings).toMatchObject({
    namespace: "shared-cluster",
    readOnlyModelsDirectories: ["D:\\Shared models"],
  });
  expect(saved?.settings).not.toHaveProperty("hfToken");
  await page.getByRole("button", { name: "General", exact: true }).click();
  await expect(page.getByLabel("Hugging Face token")).toHaveValue("");
  await page.screenshot({ path: "test-results/settings.png", fullPage: true });
});
test("external processes remain read-only and offline settings disable update controls", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.assign(window, { __EXO_STATUS_OVERRIDE__: "External" }),
  );
  await page.goto("/");
  await expect(page.getByRole("checkbox", { name: "Run EXO" })).toBeDisabled();
  await page
    .getByRole("button", { name: "Show instances", exact: true })
    .click();
  await page.getByText("Qwen3").click();
  await expect(
    page.getByRole("button", { name: "Stop instance" }),
  ).toBeDisabled();
  await page.goto("/?view=settings");
  await page.getByRole("checkbox", { name: "Offline mode" }).check();
  await page.getByRole("button", { name: "About", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Check for Updates" }),
  ).toBeDisabled();
});
test("protected runtime variables are rejected before credentials or settings are submitted", async ({
  page,
}) => {
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "Environment", exact: true }).click();
  await page.getByRole("button", { name: "Add Variable", exact: true }).click();
  await page.getByLabel("Variable name").fill("Path");
  await page.getByLabel("Variable value").fill("C:\\fake-runtime");
  await page.getByRole("button", { name: "Save & Restart" }).click();
  await expect(page.getByRole("alert")).toContainText("managed");
  expect(
    await page.evaluate(() =>
      (
        window as unknown as { __EXO_CALLS__: { command: string }[] }
      ).__EXO_CALLS__.some((call) => call.command === "save_settings"),
    ),
  ).toBe(false);
});
test("local-network setup exposes only a fixed owned-backend action", async ({
  page,
}) => {
  await page.setViewportSize({ width: 640, height: 560 });
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  await page
    .getByRole("button", { name: "Allow EXO on Local Network…" })
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "test-results/firewall-settings.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Allow EXO on Local Network…" })
    .click();
  const calls = await page.evaluate(
    () =>
      (
        window as unknown as {
          __EXO_CALLS__: { command: string; args: Record<string, unknown> }[];
        }
      ).__EXO_CALLS__,
  );
  expect(
    calls.find((call) => call.command === "configure_firewall")?.args,
  ).toEqual({});
  await page.addInitScript(() =>
    Object.assign(window, { __EXO_STATUS_OVERRIDE__: "External" }),
  );
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  for (const name of [
    "Allow EXO on Local Network…",
    "Reset Onboarding",
    "Uninstall EXO…",
  ])
    await expect(page.getByRole("button", { name })).toBeDisabled();
});
test("uninstall confirmation contains keyboard focus and Escape returns to its trigger", async ({
  page,
}) => {
  await page.goto("/?view=settings");
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  const trigger = page.getByRole("button", { name: "Uninstall EXO…" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", {
    name: "Uninstall EXO",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await expect
    .poll(() =>
      dialog.evaluate((element) => element.contains(document.activeElement)),
    )
    .toBe(true);
  for (let index = 0; index < 16; index++) {
    await page.keyboard.press(index < 8 ? "Tab" : "Shift+Tab");
    await expect
      .poll(() =>
        dialog.evaluate((element) => element.contains(document.activeElement)),
      )
      .toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  expect(
    await page.evaluate(() =>
      (
        window as unknown as { __EXO_CALLS__: { command: string }[] }
      ).__EXO_CALLS__.some((call) => call.command === "uninstall_app"),
    ),
  ).toBe(false);
});
test("task details Escape closes the dialog without hiding the tray", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Show instances", exact: true })
    .click();
  await page.getByText("Qwen3").click();
  const trigger = page.getByRole("button", { name: /TextGeneration/ });
  await trigger.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  expect(
    await page.evaluate(() =>
      (
        window as unknown as { __EXO_CALLS__: { command: string }[] }
      ).__EXO_CALLS__.some((call) => call.command === "hide_window"),
    ),
  ).toBe(false);
  await page.keyboard.press("Escape");
  expect(
    await page.evaluate(() =>
      (
        window as unknown as { __EXO_CALLS__: { command: string }[] }
      ).__EXO_CALLS__.some((call) => call.command === "hide_window"),
    ),
  ).toBe(true);
});
for (const scale of [1, 1.25, 1.5, 2]) {
  test.describe(`browser pixel density ${scale}`, () => {
    test.use({ deviceScaleFactor: scale });
    test("settings remain reachable at the minimum logical window size", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 640, height: 520 });
      await page.goto("/?view=settings");
      expect(await page.evaluate(() => window.devicePixelRatio)).toBe(scale);
      for (const name of [
        "General",
        "Model",
        "Advanced",
        "Environment",
        "About",
      ]) {
        await page.getByRole("button", { name, exact: true }).click();
        const save = page.getByRole("button", { name: "Save & Restart" });
        if (name === "About") await expect(save).toHaveCount(0);
        else await expect(save).toBeVisible();
      }
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `test-results/settings-density-${scale}.png`,
      });
    });
  });
}
test("captured frozen runtime data renders in the tray with N/A system metrics", async ({
  page,
}) => {
  test.skip(
    !liveStatePath,
    "Set EXO_DESKTOP_LIVE_STATE after the explicit frozen runtime probe.",
  );
  const state = JSON.parse(readFileSync(liveStatePath!, "utf8"));
  const nodeId = state.topology.nodes[0];
  await page.addInitScript(
    ({ state, nodeId }) =>
      Object.assign(window, {
        __EXO_STATE_OVERRIDE__: state,
        __EXO_NODE_OVERRIDE__: nodeId,
      }),
    { state, nodeId },
  );
  await page.setViewportSize({ width: 340, height: 650 });
  await page.goto("/");
  await page.getByRole("button", { name: "Show nodes", exact: true }).click();
  await expect(page.locator(".node summary").first()).toContainText(
    state.nodeIdentities[nodeId].friendlyName,
  );
  await page.locator(".node summary").first().click();
  if (
    Object.values(state.downloads)
      .flat()
      .every(
        (download: unknown) =>
          "DownloadPending" in (download as object) ||
          "DownloadCompleted" in (download as object),
      )
  )
    await expect(
      page.getByRole("button", { name: "Cancel", exact: true }),
    ).toHaveCount(0);
  if (!state.nodeSystem[nodeId])
    await expect(
      page.locator(".node dd").filter({ hasText: /^N\/A$/ }),
    ).toHaveCount(4);
  await page
    .locator(".node dt")
    .filter({ hasText: /^System power$/ })
    .scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/live-tray.png", fullPage: true });
});
