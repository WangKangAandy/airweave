/**
 * Copy text to the system clipboard.
 * Tries `navigator.clipboard.writeText` first, then a hidden `<textarea>` + `execCommand`
 * fallback (helps when the document is not focused or clipboard API rejects, e.g. some embedded contexts).
 */
export async function copyTextToClipboard(text: string): Promise<boolean> {
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch {
        // Fall through to legacy path
    }
    return fallbackCopyTextToClipboard(text);
}

function fallbackCopyTextToClipboard(value: string): boolean {
    const textArea = document.createElement("textarea");
    textArea.value = value;
    textArea.setAttribute("readonly", "");
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(textArea);
    return copied;
}
