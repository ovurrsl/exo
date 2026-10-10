// Runs only through this helper's native eval callback. No production bridge mock.
(() => {
  try {
    const rect = (element) => {
      if (!element) return null;
      const box = element.getBoundingClientRect();
      return {
        x: box.x,
        y: box.y,
        width: box.width,
        height: box.height,
        right: box.right,
        bottom: box.bottom,
      };
    };
    const positive = (box) => box && box.width > 0 && box.height > 0;
    const nav = document.querySelector("nav.tabs");
    const main = document.querySelector("main.settings-content");
    const buttons = Array.from(nav?.querySelectorAll("button") ?? []);
    const activeTab = nav
      ?.querySelector("button.active span")
      ?.textContent.trim();
    const label = (text) =>
      Array.from(main?.querySelectorAll("label") ?? []).find((item) =>
        item.textContent.replace(/\s+/g, " ").trim().includes(text),
      );
    const markers = {
      General: () => label("Cluster namespace"),
      Model: () => label("Enable image models"),
      Advanced: () => label("Fast synchronization"),
      Environment: () => label("Default writable directory"),
      About: () => main?.querySelector("h1"),
    };
    const marker = markers[activeTab]?.();
    const footer = document.querySelector(".settings-footer");
    const footerBox = rect(footer);
    const aboutValue = (name) =>
      Array.from(main?.querySelectorAll("dt") ?? [])
        .find((item) => item.textContent === name)
        ?.nextElementSibling?.textContent.trim();
    const image = main?.querySelector("img.about-icon");
    const modelButton = Array.from(main?.querySelectorAll("button") ?? []).find(
      (item) => item.textContent.includes("Manage models"),
    );
    return {
      url: location.href,
      readyState: document.readyState,
      activeTab,
      tabs: buttons.map((button) =>
        button.querySelector("span")?.textContent.trim(),
      ),
      positiveRects: [
        rect(document.querySelector(".settings-window")),
        rect(nav),
        rect(main),
        ...buttons.map(rect),
      ].every(positive),
      cssLoaded:
        Array.from(document.styleSheets).some(
          (sheet) =>
            sheet.href?.includes("/assets/") && sheet.cssRules.length > 0,
        ) && Boolean(nav && getComputedStyle(nav).display === "flex"),
      appearance: {
        surface: getComputedStyle(document.documentElement)
          .getPropertyValue("--surface")
          .trim(),
        fontFamily: getComputedStyle(document.documentElement).fontFamily,
        dark: matchMedia("(prefers-color-scheme: dark)").matches,
      },
      marker: Boolean(marker),
      markerRect: Boolean(positive(rect(marker))),
      rects: {
        nav: rect(nav),
        main: rect(main),
        marker: rect(marker),
        footer: footerBox,
        tabs: buttons.map(rect),
      },
      viewport: { width: innerWidth, height: innerHeight, devicePixelRatio },
      errors: window.__nativeSettingsProbeErrors ?? [
        "Missing test error collector",
      ],
      alerts: Array.from(document.querySelectorAll('[role="alert"]')).map(
        (item) => item.textContent,
      ),
      probeError: null,
      namespace: label("Cluster namespace")?.querySelector("input")?.value,
      versionPlaceholder:
        label("Cluster namespace")?.querySelector("input")?.placeholder,
      tokenPlaceholder:
        label("Hugging Face token")?.querySelector("input")?.placeholder,
      offline: label("Offline mode")?.querySelector("input")?.checked,
      startOnLogin: label("Start EXO when I sign in")?.querySelector("input")
        ?.checked,
      footer: Boolean(footer),
      footerInViewport: Boolean(
        positive(footerBox) &&
        footerBox.x >= 0 &&
        footerBox.y >= 0 &&
        footerBox.right <= innerWidth + 1 &&
        footerBox.bottom <= innerHeight + 1,
      ),
      saveDisabled: footer?.querySelector("button")?.disabled,
      footerText: footer?.textContent.trim(),
      aboutVersion: aboutValue("Version"),
      aboutData: aboutValue("App data"),
      imageLoaded: Boolean(image?.complete && image.naturalWidth > 0),
      manageModelsDisabled: modelButton?.disabled,
      userAgent: navigator.userAgent,
    };
  } catch (error) {
    return { probeError: String(error) };
  }
})();
