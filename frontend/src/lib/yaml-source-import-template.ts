/** 1-based column where `#` starts for inline comments (vertical alignment). */
const YAML_INLINE_COMMENT_COL = 88;

/** Pad `left` so `# comment` starts at column YAML_INLINE_COMMENT_COL. */
function yamlLineWithComment(leftPart: string, comment: string): string {
  const left = leftPart.trimEnd();
  const beforeHashLen = YAML_INLINE_COMMENT_COL - 1;
  if (left.length >= beforeHashLen) {
    return `${left}  # ${comment}`;
  }
  return `${left.padEnd(beforeHashLen)}# ${comment}`;
}

/** Full YAML example for POST /source-connections/import-yaml (must stay in sync with backend FIELD_SPECS). */
export const YAML_SOURCE_IMPORT_TEMPLATE = [
  "# Airweave bulk source import — top-level keys like version / team are optional metadata (not validated).",
  "# Layout: sources.<source_type>.<connection_display_name>: { ...credentials and config... }",
  "# Optional per-connection key: description (string, max 255). If omitted, defaults to:",
  '#   "<Source display name> connection for <collection name>" (same as the create UI).',
  "# Inline comments after values are standard YAML and are not loaded into fields.",
  "# Supported types: github, gitlab, local_git, dingtalk, confluence",
  "# Replace env-style placeholders and paths/URLs before Validate / Import.",
  "",
  yamlLineWithComment("version: 1.0.0", "document format version"),
  yamlLineWithComment('team: ""', "optional; reserved for future use"),
  "",
  yamlLineWithComment("sources:", "source type → named connections"),
  yamlLineWithComment("  github:", "source type"),
  yamlLineWithComment("    Example GitHub:", "connection display name"),
  yamlLineWithComment(
    '      description: "Docs repo — engineering handbook"',
    "optional; max 255 characters"
  ),
  yamlLineWithComment("      personal_access_token: ${GITHUB_PAT}", "required"),
  yamlLineWithComment("      repo_name: owner/repository", "required"),
  yamlLineWithComment("      branch: main", "optional"),
  yamlLineWithComment("      sync_pull_requests: false", "optional"),
  "",
  yamlLineWithComment("  gitlab:", "source type"),
  yamlLineWithComment("    Example GitLab:", "connection display name"),
  yamlLineWithComment("      personal_access_token: ${GITLAB_TOKEN}", "required"),
  yamlLineWithComment("      repo_url: https://gitlab.com/group/project.git", "required"),
  yamlLineWithComment("      branch: main", "optional"),
  "",
  yamlLineWithComment("  local_git:", "source type"),
  yamlLineWithComment("    Example Local Git:", "connection display name"),
  yamlLineWithComment("      repo_path: /absolute/path/to/git/repository", "required"),
  yamlLineWithComment("      branch: main", "optional"),
  yamlLineWithComment("      follow_symlinks: false", "optional"),
  "",
  yamlLineWithComment("  dingtalk:", "source type"),
  yamlLineWithComment("    Example DingTalk Docs:", "connection display name"),
  yamlLineWithComment("      app_key: ${DINGTALK_APP_KEY}", "required"),
  yamlLineWithComment("      app_secret: ${DINGTALK_APP_SECRET}", "required"),
  yamlLineWithComment(
    '      links: "https://alidocs.dingtalk.com/i/nodes/your-doc-or-wiki-link"',
    "required"
  ),
  yamlLineWithComment("      operator_union_id: ${DINGTALK_OPERATOR_UNION_ID}", "required"),
  "",
  yamlLineWithComment("  confluence:", "source type"),
  yamlLineWithComment("    Example Confluence:", "connection display name"),
  yamlLineWithComment("      personal_access_token: ${CONFLUENCE_API_TOKEN}", "required"),
  yamlLineWithComment("      site_url: https://your-domain.atlassian.net", "required"),
].join("\n");

export const YAML_SOURCE_IMPORT_TEMPLATE_FILENAME = "airweave-sources-import-template.yaml";
