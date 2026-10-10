<script lang="ts">
  import { onMount } from "svelte";
  import { call } from "./lib/bridge";
  import { modal } from "./lib/modal";
  import {
    formatBytes,
    parseCluster,
    validateEnvironment,
  } from "./lib/cluster";
  import type {
    Cluster,
    SavedSettings,
    Settings,
    Snapshot,
    Task,
  } from "./lib/types";
  const settingsWindow =
    new URLSearchParams(window.location.search).get("view") === "settings";
  const tabs = [
    "General",
    "Model",
    "Advanced",
    "Environment",
    "About",
  ] as const;
  let tab = $state<(typeof tabs)[number]>("General");
  let snapshot = $state<Snapshot | null>(null);
  let cluster = $state<Cluster>(parseCluster({}));
  let settings = $state<Settings | null>(null);
  let token = $state("");
  let tokenPresent = $state(false);
  let clearToken = $state(false);
  let environment = $state<{ key: string; value: string }[]>([]);
  let busy = $state(false);
  let error = $state("");
  let notice = $state("");
  let showAllNodes = $state(false);
  let showAllInstances = $state(false);
  let task = $state<Task | null>(null);
  let network = $state("");
  let uninstall = $state(false);
  let keepModels = $state(true);
  let bugReport = $state(false);
  let reportDescription = $state("");
  let welcome = $state(false);
  let countdown = $state(10);
  let pollActive = false;
  let welcomeShown = false;
  const running = $derived(snapshot?.status === "Running");
  const owned = $derived(snapshot?.owned === true);
  const offline = $derived(
    environment
      .find((item) => item.key.toUpperCase() === "EXO_OFFLINE")
      ?.value.toLowerCase() === "true" ||
      (settings?.offline === true &&
        !environment.some((item) => item.key.toUpperCase() === "EXO_OFFLINE")),
  );
  const usedMemory = $derived(
    cluster.nodes.reduce(
      (sum, node) => sum + Math.max(0, node.total - node.available),
      0,
    ),
  );
  const totalMemory = $derived(
    cluster.nodes.reduce((sum, node) => sum + node.total, 0),
  );
  const visibleNodes = $derived(
    showAllNodes ? cluster.nodes : cluster.nodes.slice(0, 3),
  );
  const visibleInstances = $derived(
    showAllInstances ? cluster.instances : cluster.instances.slice(0, 3),
  );
  // Pending/completed statuses describe the model inventory, including models
  // never requested. Keep the tray's controls on actual transfers and failures.
  const currentDownloads = $derived(
    cluster.downloads.filter((download) =>
      ["Ongoing", "Failed"].includes(download.kind),
    ),
  );
  async function action(operation: () => Promise<unknown>, success = "") {
    busy = true;
    error = "";
    notice = "";
    try {
      await operation();
      if (success) notice = success;
      await refresh();
    } catch (reason) {
      error = String(reason);
    } finally {
      busy = false;
    }
  }
  async function refresh() {
    if (pollActive) return;
    pollActive = true;
    try {
      snapshot = await call<Snapshot>("snapshot");
      if (snapshot.status === "Running" || snapshot.status === "External")
        cluster = parseCluster(await call("cluster_state"));
      else if (snapshot.status === "Stopped") cluster = parseCluster({});
      if (
        !settingsWindow &&
        running &&
        !welcomeShown &&
        settings &&
        !settings.onboardingCompleted
      ) {
        welcomeShown = true;
        welcome = true;
        countdown = 10;
      }
    } catch (reason) {
      error = String(reason);
    } finally {
      pollActive = false;
    }
  }
  async function loadSettings() {
    const saved = await call<SavedSettings>("get_settings");
    settings = saved.settings;
    tokenPresent = saved.hfTokenPresent;
    environment = Object.entries(saved.settings.customEnvironment).map(
      ([key, value]) => ({ key, value }),
    );
  }
  async function saveSettings() {
    if (!settings) return;
    await action(async () => {
      const saved = await call<SavedSettings>("save_settings", {
        settings: {
          ...settings!,
          customEnvironment: validateEnvironment(environment),
        },
        hfToken: token || null,
        clearHfToken: clearToken,
      });
      settings = saved.settings;
      tokenPresent = saved.hfTokenPresent;
      token = "";
      clearToken = false;
    }, "Saved. The running backend restarts with these settings.");
  }
  async function dashboard(section = "") {
    welcome = false;
    await action(() => call("open_dashboard", { section }));
  }
  async function exportDiagnostics() {
    await action(async () => {
      const path = await call<string | null>("export_diagnostics");
      if (path) notice = `Diagnostics ZIP saved: ${path}`;
    });
  }
  async function directory(which: "default" | "additional" | "readonly") {
    const path = await call<string | null>("pick_directory");
    if (!path || !settings) return;
    if (which === "default") settings.defaultModelsDirectory = path;
    else if (which === "additional")
      settings.additionalModelsDirectories = [
        ...settings.additionalModelsDirectories,
        path,
      ];
    else
      settings.readOnlyModelsDirectories = [
        ...settings.readOnlyModelsDirectories,
        path,
      ];
  }
  function position(index: number) {
    const angle =
      (index * Math.PI * 2) / Math.max(1, cluster.nodes.length) - Math.PI / 2;
    return {
      x: 155 + Math.cos(angle) * (cluster.nodes.length === 1 ? 0 : 88),
      y: 75 + Math.sin(angle) * (cluster.nodes.length === 1 ? 0 : 46),
    };
  }
  function nodePosition(id: string) {
    return position(
      Math.max(
        0,
        cluster.nodes.findIndex((node) => node.id === id),
      ),
    );
  }
  onMount(() => {
    void loadSettings()
      .then(refresh)
      .catch((reason) => (error = String(reason)));
    const polling = setInterval(() => void refresh(), 1000);
    const welcomeTimer = setInterval(() => {
      if (welcome && countdown > 0) countdown--;
      else if (welcome && countdown === 0) void dashboard();
    }, 1000);
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !document.querySelector("dialog:modal")) {
        task = null;
        uninstall = false;
        bugReport = false;
        welcome = false;
        if (!settingsWindow) void call("hide_window");
      }
    };
    window.addEventListener("keydown", keyboard);
    return () => {
      clearInterval(polling);
      clearInterval(welcomeTimer);
      window.removeEventListener("keydown", keyboard);
    };
  });
</script>

<div class:settings-window={settingsWindow} class="desktop">
  <header>
    <div class="brand">
      <img src="/icon.png" alt="" /><strong>EXO</strong><span
        >{settingsWindow ? "Settings" : "Windows"}</span
      >
    </div>
    <button
      class="icon"
      aria-label="Close window"
      onclick={() => call("hide_window")}>×</button
    >
  </header>
  {#if error}<div class="message error" role="alert">
      {error}<button aria-label="Dismiss error" onclick={() => (error = "")}
        >×</button
      >
    </div>{/if}
  {#if notice}<div class="message notice" role="status">{notice}</div>{/if}
  {#if !settingsWindow}
    <main class="popover">
      <section class="status-row">
        <div>
          <span
            class:online={running}
            class:external={snapshot?.status === "External"}
            class="status-dot"
          ></span><strong>{snapshot?.status ?? "Connecting to desktop…"}</strong
          >
        </div>
        <label class="switch"
          ><input
            aria-label="Run EXO"
            type="checkbox"
            checked={running || snapshot?.status === "Starting"}
            disabled={snapshot?.status === "External" ||
              snapshot?.status === "Stopping"}
            onchange={(event) =>
              action(() =>
                call(
                  event.currentTarget.checked
                    ? "start_backend"
                    : "stop_backend",
                ),
              )}
          /><span></span></label
        >
      </section>
      {#if snapshot?.detail}<p class="muted detail">{snapshot.detail}</p>{/if}
      {#if snapshot?.status === "External"}<p class="message">
          An EXO process already owns the API port. This view is read-only; stop
          that process to let this desktop manage EXO.
        </p>{/if}
      <section class="overview">
        <div
          title="Used and reserved compute memory. Windows CUDA availability includes a runtime safety reserve; this value can differ from physical GPU usage."
        >
          <strong>{formatBytes(usedMemory)}</strong><span
            >of {formatBytes(totalMemory)}</span
          ><small>Cluster compute memory</small>
        </div>
        <div><strong>{cluster.nodes.length}</strong><small>Nodes</small></div>
        <div>
          <strong>{cluster.instances.length}</strong><small>Instances</small>
        </div>
      </section>
      <div class="cluster-scroll">
        <section>
          <h2>Topology</h2>
          {#if cluster.nodes.length}
            <svg
              class="topology"
              viewBox="0 0 310 165"
              role="img"
              aria-label="Cluster network topology"
              ><title>Cluster network topology</title>
              {#each cluster.edges as edge}<line
                  x1={nodePosition(edge.source).x}
                  y1={nodePosition(edge.source).y}
                  x2={nodePosition(edge.target).x}
                  y2={nodePosition(edge.target).y}
                  class:rdma={edge.rdma}
                />{/each}
              {#each cluster.nodes as node, index}<circle
                  cx={position(index).x}
                  cy={position(index).y}
                  r="14"
                  class:local={node.id === snapshot?.nodeId}
                /><text
                  x={position(index).x}
                  y={position(index).y + 30}
                  text-anchor="middle">{node.name.slice(0, 17)}</text
                >{/each}
            </svg>
          {:else}<p class="empty">
              {running
                ? "Discovering devices on your network…"
                : "Start EXO to connect your devices."}
            </p>{/if}
        </section>
        <section>
          <div class="section-heading">
            <h2>Nodes</h2>
            {#if cluster.nodes.length > 3}<button
                class="link"
                onclick={() => (showAllNodes = !showAllNodes)}
                >{showAllNodes ? "Show less" : "Show all"}</button
              >{/if}
          </div>
          {#each visibleNodes as node}<details class="card node">
              <summary
                ><div>
                  <strong>{node.name}</strong><small
                    >{node.chip || node.os}</small
                  >
                </div>
                <span
                  title={node.backends.includes("MlxCuda")
                    ? "Used and reserved compute memory, including the Windows CUDA runtime safety reserve. This can differ from physical GPU usage."
                    : "Used compute memory / total compute memory"}
                  >{formatBytes(node.total - node.available)} / {formatBytes(
                    node.total,
                  )}</span
                ></summary
              ><progress
                value={Math.max(0, node.total - node.available)}
                max={node.total || 1}
              ></progress>
              <dl>
                <dt>CPU</dt>
                <dd>
                  {node.cpu === null ? "N/A" : `${Math.round(node.cpu * 100)}%`}
                </dd>
                <dt>GPU</dt>
                <dd>
                  {node.gpu === null ? "N/A" : `${Math.round(node.gpu * 100)}%`}
                </dd>
                <dt>Temperature</dt>
                <dd>
                  {node.temperature === null || node.temperature === 0
                    ? "N/A"
                    : `${node.temperature.toFixed(1)} °C`}
                </dd>
                <dt>System power</dt>
                <dd>
                  {node.power === null || node.power === 0
                    ? "N/A"
                    : `${node.power.toFixed(1)} W`}
                </dd>
                <dt>Backend</dt>
                <dd>{node.backends.join(", ") || "Unknown"}</dd>
                <dt>Operating system</dt>
                <dd>{node.os || "Unknown"}</dd>
                <dt>Node ID</dt>
                <dd class="mono">{node.id}</dd>
              </dl>
            </details>{/each}
        </section>
        <section>
          <div class="section-heading">
            <h2>Instances</h2>
            {#if cluster.instances.length > 3}<button
                class="link"
                onclick={() => (showAllInstances = !showAllInstances)}
                >{showAllInstances ? "Show less" : "Show all"}</button
              >{/if}
          </div>
          {#each visibleInstances as instance}<details class="card">
              <summary
                ><div>
                  <strong>{instance.model.split("/").at(-1)}</strong><small
                    >{instance.nodes.length} node(s) · {instance.kind.replace(
                      "Instance",
                      "",
                    )}</small
                  >
                </div></summary
              >
              <p class="muted">{instance.status}</p>
              {#each instance.tasks as item}<button
                  class="task"
                  onclick={() => (task = item)}
                  ><span>{item.kind}</span><span>{item.status}</span></button
                >{/each}
              <button
                class="danger small"
                disabled={!owned || busy}
                onclick={() =>
                  action(() =>
                    call("delete_instance", { instanceId: instance.id }),
                  )}>Stop instance</button
              >
            </details>
          {:else}<p class="empty">Choose a model in the dashboard.</p>{/each}
        </section>
        {#if currentDownloads.length}<section>
            <h2>Downloads</h2>
            {#each currentDownloads as download}<div class="card">
                <strong>{download.model.split("/").at(-1)}</strong><small
                  >{cluster.nodes.find((node) => node.id === download.node)
                    ?.name ?? download.node.slice(0, 8)} · {download.kind}</small
                >{#if download.total > 0}<progress
                    value={download.kind === "Completed"
                      ? download.total
                      : download.downloaded}
                    max={download.total}
                  ></progress><small
                    >{formatBytes(download.downloaded)} / {formatBytes(
                      download.total,
                    )}{download.speed > 0
                      ? ` · ${formatBytes(download.speed)}/s · ${Math.ceil(download.eta / 1000)}s`
                      : ""}</small
                  >{/if}{#if download.error}<p class="error-text">
                    {download.error}
                  </p>{/if}{#if download.kind === "Ongoing"}<button
                    disabled={!owned || busy}
                    class="small"
                    onclick={() =>
                      action(() =>
                        call("cancel_download", {
                          nodeId: download.node,
                          modelId: download.model,
                        }),
                      )}>Cancel</button
                  >{:else if download.kind === "Failed"}<button
                    disabled={!owned || busy}
                    class="small"
                    onclick={() =>
                      action(() =>
                        call("retry_download", {
                          nodeId: download.node,
                          shard: download.shard,
                        }),
                      )}>Retry</button
                  >{/if}{#if download.readOnly}<small
                    >Read-only model directory</small
                  >{/if}
              </div>{/each}
          </section>{/if}
      </div>
      {#if welcome}<aside class="welcome">
          <strong>EXO is running</strong>
          <p>Connect devices and choose a model in the dashboard.</p>
          <button class="primary" onclick={() => dashboard()}
            >Open Dashboard</button
          ><small
            >Opening in {countdown}s
            <button class="link" onclick={() => (welcome = false)}
              >Cancel</button
            ></small
          >
        </aside>{/if}
      <button
        class="primary full"
        disabled={!running && snapshot?.status !== "External"}
        onclick={() => dashboard()}>Web Dashboard ↗</button
      >
      <div class="button-row">
        <button
          disabled={!running && snapshot?.status !== "External"}
          onclick={() => action(() => call("copy_api_url"), "API URL copied.")}
          >Copy API URL</button
        ><button onclick={() => action(() => call("show_settings"))}
          >Settings…</button
        >
      </div>
      <div class="footer-actions">
        <button
          disabled={busy || offline}
          onclick={() =>
            action(() => call("check_update"), "Update check complete.")}
          >Check for Updates</button
        ><button onclick={() => (bugReport = true)}>Bug Report</button><button
          onclick={() => action(() => call("quit_app"))}>Quit</button
        >
      </div>
      {#if snapshot?.update}<aside class="message notice">
          Version {snapshot.update.version} is available.
          <button
            disabled={busy}
            onclick={() => action(() => call("install_update"))}
            >Install Update</button
          >
        </aside>{/if}
    </main>
  {:else}
    <nav class="tabs" aria-label="Settings sections">
      {#each tabs as name}<button
          class:active={tab === name}
          onclick={() => (tab = name)}>{name}</button
        >{/each}
    </nav>
    <main class="settings-content">
      {#if settings}
        {#if tab === "General"}
          <h1>General</h1>
          <label
            >Cluster namespace<input
              bind:value={settings.namespace}
              placeholder={snapshot?.version ?? "Release version"}
            /></label
          >
          <p class="muted">
            Use the same namespace on every device in your cluster.
          </p>
          <label
            >Hugging Face token<input
              type="password"
              bind:value={token}
              autocomplete="new-password"
              placeholder={tokenPresent
                ? "Saved in Windows Credential Manager"
                : "Optional token"}
            /></label
          >{#if tokenPresent}<label class="check"
              ><input type="checkbox" bind:checked={clearToken} />Remove saved
              token</label
            >{/if}
          <label
            >Hugging Face endpoint<input
              bind:value={settings.hfEndpoint}
              placeholder="https://huggingface.co"
            /></label
          >
          <label class="check"
            ><input type="checkbox" bind:checked={settings.offline} />Offline
            mode</label
          >
          <p class="muted">
            Use downloaded models; pause network update checks.
          </p>
          <label class="check"
            ><input type="checkbox" bind:checked={settings.startOnLogin} />Start
            EXO when I sign in</label
          >
        {:else if tab === "Model"}
          <h1>Models</h1>
          <label class="check"
            ><input
              type="checkbox"
              bind:checked={settings.enableImageModels}
            />Enable image models</label
          >
          <p class="muted">
            Models are shown according to the capabilities of connected devices.
          </p>
          <button
            disabled={!running && snapshot?.status !== "External"}
            onclick={() => dashboard()}>Manage models in Dashboard ↗</button
          >
        {:else if tab === "Advanced"}
          <h1>Advanced</h1>
          <label class="check"
            ><input type="checkbox" bind:checked={settings.fastSynch} />Fast
            synchronization</label
          >
          <p class="muted">
            The engine uses this setting only on supported backends.
          </p>
          <h2>Onboarding</h2>
          <button
            disabled={busy || snapshot?.status === "External"}
            onclick={() =>
              action(
                () => call("reset_onboarding"),
                "Onboarding reset; the dashboard wizard will open.",
              )}>Reset Onboarding</button
          >
          <h2>Network diagnostics</h2>
          <p class="muted">
            Check Windows adapters, NVIDIA devices, firewall profiles and
            cluster connectivity.
          </p>
          <p class="muted">
            Allow EXO on private or domain networks for devices on your local
            subnet. Windows asks for administrator permission. Rules target only
            this installed EXO runtime.
          </p>
          <button
            disabled={busy || !running || !owned}
            onclick={() =>
              action(
                () => call("configure_firewall"),
                "EXO local cluster firewall rules are configured.",
              )}>Allow EXO on Local Network…</button
          >
          <div class="button-row">
            <button
              disabled={busy}
              onclick={() =>
                action(async () => {
                  network = await call<string>("network_diagnostics");
                })}>Collect Diagnostics</button
            ><button
              onclick={() =>
                action(() => call("open_location", { location: "network" }))}
              >Network Settings ↗</button
            >
          </div>
          {#if network}<pre class="diagnostics">{network}</pre>{/if}
          <div class="button-row">
            <button
              onclick={() =>
                action(() => call("open_location", { location: "logs" }))}
              >Open Logs</button
            ><button onclick={exportDiagnostics}>Export Diagnostics ZIP</button>
          </div>
          <h2>Uninstall</h2>
          <button
            class="danger"
            disabled={busy || snapshot?.status === "External"}
            onclick={() => (uninstall = true)}>Uninstall EXO…</button
          >
        {:else if tab === "Environment"}
          <h1>Model directories</h1>
          <label
            >Default writable directory
            <div class="input-row">
              <input
                bind:value={settings.defaultModelsDirectory}
                placeholder={`${snapshot?.dataPath ?? "%LOCALAPPDATA%\\exo"}\\models`}
              /><button onclick={() => action(() => directory("default"))}
                >Browse…</button
              >
            </div></label
          >
          <h2>Additional writable directories</h2>
          {#each settings.additionalModelsDirectories as path, index}<div
              class="input-row"
            >
              <input
                value={path}
                aria-label="Additional writable directory"
                oninput={(event) =>
                  (settings!.additionalModelsDirectories[index] =
                    event.currentTarget.value)}
              /><button
                aria-label="Remove writable directory"
                onclick={() =>
                  (settings!.additionalModelsDirectories =
                    settings!.additionalModelsDirectories.filter(
                      (_, i) => i !== index,
                    ))}>×</button
              >
            </div>{/each}<button
            onclick={() => action(() => directory("additional"))}
            >Add Directory…</button
          >
          <h2>Read-only model directories</h2>
          {#each settings.readOnlyModelsDirectories as path, index}<div
              class="input-row"
            >
              <input
                value={path}
                aria-label="Read-only model directory"
                oninput={(event) =>
                  (settings!.readOnlyModelsDirectories[index] =
                    event.currentTarget.value)}
              /><button
                aria-label="Remove read-only directory"
                onclick={() =>
                  (settings!.readOnlyModelsDirectories =
                    settings!.readOnlyModelsDirectories.filter(
                      (_, i) => i !== index,
                    ))}>×</button
              >
            </div>{/each}<button
            onclick={() => action(() => directory("readonly"))}
            >Add Read-only Directory…</button
          >
          <p class="muted">
            EXO never writes to or deletes files from read-only directories.
          </p>
          <h2>Custom environment variables</h2>
          {#each environment as variable, index}<div class="environment-row">
              <input
                aria-label="Variable name"
                placeholder="NAME"
                bind:value={variable.key}
              /><input
                aria-label="Variable value"
                placeholder="Value"
                bind:value={variable.value}
              /><button
                aria-label="Remove environment variable"
                onclick={() =>
                  (environment = environment.filter((_, i) => i !== index))}
                >×</button
              >
            </div>{/each}<button
            onclick={() =>
              (environment = [...environment, { key: "", value: "" }])}
            >Add Variable</button
          >
          <p class="muted">
            Custom values override the related settings. Windows names are
            case-insensitive.
          </p>
        {:else}
          <h1>About EXO</h1>
          <img class="about-icon" src="/icon.png" alt="EXO logo" />
          <dl>
            <dt>Version</dt>
            <dd>{snapshot?.version}</dd>
            <dt>Engine commit</dt>
            <dd class="mono">{snapshot?.sourceCommit ?? "N/A"}</dd>
            <dt>MLX runtime</dt>
            <dd>{snapshot?.mlxVersion ?? "N/A"}</dd>
            <dt>Runtime</dt>
            <dd class="mono">{snapshot?.runtimePath}</dd>
            <dt>App data</dt>
            <dd class="mono">{snapshot?.dataPath}</dd>
            <dt>Updates</dt>
            <dd>
              {snapshot?.updaterConfigured
                ? "Signed Windows release feed"
                : "This build has no update signing key configured."}
            </dd>
          </dl>
          {#if snapshot?.sourceModified}<p class="muted">Working tree changes included.</p>{/if}
          <div class="button-row">
            <button
              disabled={busy || offline}
              onclick={() =>
                action(() => call("check_update"), "Update check complete.")}
              >Check for Updates</button
            ><button
              onclick={() =>
                action(() => call("open_issue", { description: "" }))}
              >Report an Issue ↗</button
            >
          </div>
          {#if snapshot?.update}<p class="notice">
              Version {snapshot.update.version} is available.
            </p>
            <p>{snapshot.update.body}</p>
            <button
              disabled={busy || offline}
              onclick={() => action(() => call("install_update"))}
              >Install Signed Update</button
            >{/if}
          <p class="muted">
            EXO connects your devices into one inference cluster. Metal on Mac,
            CUDA on Windows; the same dashboard and APIs.
          </p>
        {/if}
      {:else}<p>Loading settings…</p>{/if}
    </main>
    <footer class="settings-footer">
      <span
        >{busy
          ? "Applying…"
          : "Settings apply on the next backend launch."}</span
      ><button
        class="primary"
        disabled={busy || !settings}
        onclick={saveSettings}>Save &amp; Restart</button
      >
    </footer>
  {/if}
</div>
{#if task}
    <dialog class="modal-dialog" use:modal={() => (task = null)} aria-labelledby="task-title">
      <h2 id="task-title">{task.kind}</h2>
      <p>{task.status}</p>
      <pre>{task.prompt}</pre>
      {#if task.error}<p class="error-text">{task.error}</p>{/if}<button
        onclick={() => (task = null)}>Close</button
      >
    </dialog>
{/if}
{#if uninstall}
    <dialog class="modal-dialog" use:modal={() => (uninstall = false)} aria-labelledby="uninstall-title">
      <h2 id="uninstall-title">Uninstall EXO</h2>
      <p>
        Stop the owned backend, remove login startup and launch the Windows
        uninstaller. Custom and read-only model directories are preserved.
      </p>
      <label class="check"
        ><input type="checkbox" bind:checked={keepModels} />Keep downloaded
        models in the default EXO data folder</label
      >
      <div class="button-row">
        <button onclick={() => (uninstall = false)}>Cancel</button><button
          class="danger"
          disabled={busy}
          onclick={() => action(() => call("uninstall_app", { keepModels }))}
          >Uninstall</button
        >
      </div>
    </dialog>
{/if}
{#if bugReport}
    <dialog class="modal-dialog" use:modal={() => (bugReport = false)} aria-labelledby="report-title">
      <h2 id="report-title">Report a Windows issue</h2>
      <label
        >What happened?<textarea
          rows="5"
          bind:value={reportDescription}
          placeholder="Describe the problem and how to reproduce it."
        ></textarea></label
      >
      <p>
        Export a local diagnostics ZIP and inspect it before attaching it to
        your issue. Nothing is uploaded automatically.
      </p>
      <div class="button-row">
        <button disabled={busy} onclick={exportDiagnostics}
          >Save Diagnostics ZIP</button
        ><button
          disabled={busy}
          class="primary"
          onclick={() =>
            action(() =>
              call("open_issue", { description: reportDescription }),
            )}>Open GitHub Draft ↗</button
        >
      </div>
      <button onclick={() => (bugReport = false)}>Close</button>
    </dialog>
{/if}
