/**
 * YAML bulk-import metadata (must stay aligned with backend
 * `SourceImportService.SUPPORTED_TYPES` and `FIELD_SPECS` in
 * `backend/airweave/domains/source_import/`).
 *
 * Order matches `YAML_SOURCE_IMPORT_TEMPLATE` top-level `sources.*` keys.
 */
export const YAML_BULK_IMPORT_TYPES_ORDER = [
    "github",
    "gitlab",
    "local_git",
    "dingtalk",
    "confluence",
] as const;

export type YamlBulkImportType = (typeof YAML_BULK_IMPORT_TYPES_ORDER)[number];

export const YAML_BULK_IMPORT_TYPE_LABELS: Record<YamlBulkImportType, string> = {
    github: "GitHub",
    gitlab: "GitLab",
    local_git: "Local Git",
    dingtalk: "DingTalk",
    confluence: "Confluence",
};

export interface YamlBulkImportFieldSpec {
    key: string;
    hint?: string;
}

export interface YamlBulkImportTypeSpec {
    type: YamlBulkImportType;
    label: string;
    /** Block indented under `sources.<type>:` (connection name + fields). */
    exampleBlock: string;
    required: YamlBulkImportFieldSpec[];
    optional: YamlBulkImportFieldSpec[];
}

/** Field specs and examples — order follows `YAML_BULK_IMPORT_TYPES_ORDER`. */
export const YAML_BULK_IMPORT_TYPE_SPECS: YamlBulkImportTypeSpec[] = [
    {
        type: "github",
        label: YAML_BULK_IMPORT_TYPE_LABELS.github,
        exampleBlock: [
            "  github:",
            "    My GitHub connection:",
            "      personal_access_token: ghp_xxxxxxxx",
            "      repo_name: owner/repository",
            "      branch: main",
            "      sync_pull_requests: false",
        ].join("\n"),
        required: [
            { key: "personal_access_token", hint: "PAT with repo scope" },
            { key: "repo_name", hint: "`owner/repo`" },
        ],
        optional: [
            { key: "branch", hint: "default branch if omitted" },
            { key: "sync_pull_requests", hint: "boolean" },
        ],
    },
    {
        type: "gitlab",
        label: YAML_BULK_IMPORT_TYPE_LABELS.gitlab,
        exampleBlock: [
            "  gitlab:",
            "    My GitLab connection:",
            "      personal_access_token: glpat-xxxxxxxx",
            "      repo_url: https://gitlab.com/group/project.git",
            "      branch: main",
        ].join("\n"),
        required: [
            { key: "personal_access_token" },
            { key: "repo_url", hint: "clone URL" },
        ],
        optional: [{ key: "branch" }],
    },
    {
        type: "local_git",
        label: YAML_BULK_IMPORT_TYPE_LABELS.local_git,
        exampleBlock: [
            "  local_git:",
            "    My local repo:",
            "      repo_path: /absolute/path/to/git/repository",
            "      branch: main",
            "      follow_symlinks: false",
        ].join("\n"),
        required: [{ key: "repo_path", hint: "absolute path on sync host" }],
        optional: [
            { key: "branch", hint: "default `main`" },
            { key: "follow_symlinks", hint: "boolean" },
        ],
    },
    {
        type: "dingtalk",
        label: YAML_BULK_IMPORT_TYPE_LABELS.dingtalk,
        exampleBlock: [
            "  dingtalk:",
            "    My DingTalk docs:",
            "      app_key: your_app_key",
            "      app_secret: your_app_secret",
            '      links: "https://alidocs.dingtalk.com/i/nodes/..."',
            "      operator_union_id: union_id_of_operator",
        ].join("\n"),
        required: [
            { key: "app_key" },
            { key: "app_secret" },
            { key: "links", hint: "DingTalk doc/wiki link(s)" },
            { key: "operator_union_id" },
        ],
        optional: [],
    },
    {
        type: "confluence",
        label: YAML_BULK_IMPORT_TYPE_LABELS.confluence,
        exampleBlock: [
            "  confluence:",
            "    My Confluence site:",
            "      personal_access_token: API_token",
            "      site_url: https://your-domain.atlassian.net",
        ].join("\n"),
        required: [
            { key: "personal_access_token", hint: "maps to API token auth" },
            { key: "site_url", hint: "Confluence Cloud base URL" },
        ],
        optional: [],
    },
];
