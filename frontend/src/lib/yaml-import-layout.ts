/**
 * Shared layout for YAML bulk-import UI: main import modal and 示例模板 preview modal.
 * Keeps width, scroll behavior, and monospace no-wrap styling consistent.
 */

/** Modal shell: wide dialog, vertical cap, no default padding (headers/footers pad themselves). */
export const yamlImportLargeModalContentClassName =
  "flex max-h-[90vh] w-[min(96vw,1280px)] max-w-[min(96vw,1280px)] flex-col gap-0 overflow-hidden p-0 sm:max-w-[min(96vw,1280px)]";

const _scrollShell =
  "flex w-full flex-1 flex-col min-h-[min(42vh,440px)] max-h-[min(55vh,560px)] rounded-md border border-border bg-muted/30";

/**
 * Scroll region for read-only `<pre>` (example template).
 * Long lines extend the `<pre>` width; outer box scrolls horizontally.
 */
export const yamlImportMonoScrollRegionForPreClassName =
  `${_scrollShell} overflow-x-auto overflow-y-auto`;

/**
 * Clip region for `<textarea>` editor: full width of modal; long lines scroll *inside* the textarea.
 * Do not use `min-w-max` on the textarea — short content would shrink the box to a few characters wide.
 */
export const yamlImportMonoScrollRegionForTextareaClassName =
  `${_scrollShell} overflow-hidden`;

/** Read-only monospace block (template preview). */
export const yamlImportMonoReadonlyClassName =
  "m-0 block min-h-full min-w-max p-3 font-mono text-xs whitespace-pre";

/**
 * Editable YAML: fills scroll region; horizontal scroll is on the control (`overflow-auto`).
 * Use with `wrap="off"` on the `<textarea>`.
 */
export const yamlImportMonoTextareaClassName =
  "m-0 box-border h-full min-h-0 w-full min-w-0 flex-1 resize-none border-0 bg-transparent p-3 font-mono text-xs whitespace-pre shadow-none outline-none overflow-auto focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-0 rounded-none";
