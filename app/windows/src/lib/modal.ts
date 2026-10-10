// Native modal dialogs make the background inert and restore focus on close.
export function modal(dialog: HTMLDialogElement, dismiss: () => void) {
  const trigger = document.activeElement;
  const cancel = (event: Event) => {
    event.preventDefault();
    dismiss();
  };
  const keyboard = (event: KeyboardEvent) => {
    if (event.key !== "Tab") return;
    const controls = Array.from(
      dialog.querySelectorAll<HTMLElement>(
        "button, input, textarea, select, a[href], summary, [tabindex]",
      ),
    ).filter(
      (element) =>
        element.tabIndex >= 0 &&
        !element.matches(":disabled") &&
        element.getClientRects().length > 0,
    );
    const first = controls[0];
    const last = controls.at(-1);
    if (!first || !last) {
      event.preventDefault();
      dialog.focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  dialog.addEventListener("cancel", cancel);
  dialog.addEventListener("keydown", keyboard);
  dialog.showModal();
  return {
    destroy() {
      dialog.removeEventListener("cancel", cancel);
      dialog.removeEventListener("keydown", keyboard);
      dialog.close();
      if (trigger instanceof HTMLElement && trigger.isConnected)
        trigger.focus();
    },
  };
}
