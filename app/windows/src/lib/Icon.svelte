<script lang="ts">
  let { name, size = 14 }: { name: string; size?: number } = $props();
  const paths: Record<string, string> = {
    dashboard: "M7 3h14v14M21 3 9 15M13 3H3v18h18V11",
    copy: "M8 8h13v13H8zM16 8V3H3v13h5",
    link: "m10 13 4-4M8 16H6a4 4 0 0 1 0-8h4M14 8h4a4 4 0 0 1 0 8h-4",
    settings:
      "m9 3-1 3-3 1-2 3 2 2-1 3 3 2 1 3h4l1-3 3-2-1-3 2-2-2-3-3-1-1-3zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
    update: "M20 7V3l-4 4M20 7a9 9 0 0 0-15 0M4 17v4l4-4M4 17a9 9 0 0 0 15 0",
    bug: "M9 7h6l3 4v7l-3 3H9l-3-3v-7zM9 7V4l3-2 3 2v3M12 11v10M2 11h4M18 11h4M2 17h4M18 17h4M4 5l4 4M20 5l-4 4",
    model: "m12 2 10 5v10l-10 5L2 17V7zM2 7l10 5 10-5M12 12v10",
    advanced:
      "m14 5 5-3-1 6-4 3-9 10-3-3 10-10zM2 3l4 1 3 4-2 2-4-3zM14 15l6 6",
    environment: "m4 6 5 6-5 6M12 18h8",
    about: "M12 7h.01M12 11v6M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20",
    desktop: "M2 3h20v13H2zM12 16v5M7 21h10",
    laptop: "M4 3h16v13H4zM2 20h20l-2-4H4z",
  };
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.5"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"><path d={paths[name] ?? paths.desktop} /></svg
>
