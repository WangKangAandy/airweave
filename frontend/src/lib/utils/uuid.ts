let fallbackUidCounter = 0;

/**
 * Generate a UUID-like id with progressive browser compatibility.
 *
 * Priority:
 * 1) crypto.randomUUID() when available
 * 2) RFC4122 v4 via crypto.getRandomValues()
 * 3) Timestamp + monotonic counter fallback
 */
export const generateUuid = (): string => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return crypto.randomUUID();
    }

    if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
        const bytes = new Uint8Array(16);
        crypto.getRandomValues(bytes);

        // RFC4122 version + variant bits
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;

        const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
        return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}`;
    }

    fallbackUidCounter += 1;
    return `fallback-${Date.now()}-${fallbackUidCounter}`;
};
