/** Max length for `SourceConnectionCreate.description` (matches backend). */
export const SOURCE_CONNECTION_DESCRIPTION_MAX_LENGTH = 255;

/**
 * Default connection description when the user leaves the optional field empty.
 * Mirrors the historical hard-coded payload in SourceConfigView.
 */
export function getDefaultSourceConnectionDescription(
  sourceDisplayName: string,
  collectionDisplayName: string
): string {
  const src = sourceDisplayName.trim() || "Source";
  const coll = collectionDisplayName.trim() || "collection";
  return `${src} connection for ${coll}`.slice(0, SOURCE_CONNECTION_DESCRIPTION_MAX_LENGTH);
}

/**
 * Final description for API: non-empty trimmed user text, or the default template.
 */
export function resolveSourceConnectionDescription(
  userInput: string | undefined,
  sourceDisplayName: string,
  collectionDisplayName: string
): string {
  const trimmed = (userInput ?? "").trim();
  if (trimmed) {
    return trimmed.slice(0, SOURCE_CONNECTION_DESCRIPTION_MAX_LENGTH);
  }
  return getDefaultSourceConnectionDescription(sourceDisplayName, collectionDisplayName);
}
