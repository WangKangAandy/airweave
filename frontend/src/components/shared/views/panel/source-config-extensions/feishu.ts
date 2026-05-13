export interface ParsedFeishuEntries {
  normalized: string;
  accepted: string[];
  invalid: string[];
}

export function parseFeishuEntries(input: string): ParsedFeishuEntries {
  const parts = input
    .split(/[\s,;，；]+/)
    .map((item) => item.trim())
    .filter(Boolean);

  const accepted: string[] = [];
  const invalid: string[] = [];

  parts.forEach((part) => {
    const folderMatch = part.match(/\/drive\/folder\/([A-Za-z0-9_-]+)/);
    const wikiMatch = part.match(/\/wiki\/([A-Za-z0-9_-]+)/);
    const docxMatch = part.match(/\/docx\/([A-Za-z0-9_-]+)/);

    if (folderMatch) {
      accepted.push(`folder:${folderMatch[1]}`);
      return;
    }
    if (wikiMatch) {
      accepted.push(`wiki:${wikiMatch[1]}`);
      return;
    }
    if (docxMatch) {
      accepted.push(`docx:${docxMatch[1]}`);
      return;
    }
    if (!part.includes("/") && !part.includes("?")) {
      const lowered = part.toLowerCase();
      if (lowered.startsWith("wik")) {
        accepted.push(`wiki:${part}`);
      } else if (lowered.startsWith("dox")) {
        accepted.push(`docx:${part}`);
      } else {
        accepted.push(`folder:${part}`);
      }
      return;
    }
    invalid.push(part);
  });

  const deduped = Array.from(new Set(accepted));
  return { normalized: deduped.join(","), accepted: deduped, invalid };
}
