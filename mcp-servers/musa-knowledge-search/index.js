#!/usr/bin/env node
/**
 * MUSA Knowledge Search MCP Server
 *
 * Based on airweave-mcp-search; uses X-API-Key auth.
 * Adds list-collection-sources with sanitization and caching.
 */

import { createHash } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const VERSION = "1.1.1";
const DEFAULT_BASE_URL = "https://api.airweave.ai";

/**
 * Airweave index/API naming vs semantics (teach agents; platform rename tracked in backend TODOs).
 * - Connection display name (e.g. "torch_musa") → table column "Source", NOT searchable via source_name.
 * - Source type / connector short_name (e.g. "github") → indexed as airweave_system_metadata.source_name (legacy field name).
 * - One specific connection when types duplicate → airweave_system_metadata.sync_id.
 */
const SOURCE_FIELD_GLOSSARY = [
  "**Source field glossary (avoid ambiguity):**",
  "| What you mean | Example | Use in filters |",
  "|---|---|---|",
  "| Connection display name | torch_musa | Not in `source_name` — use `sync_id` from this list, or search without that filter |",
  "| Source type (connector) | github, confluence | `airweave_system_metadata.source_name` (= type today; API may add `source_type` later) |",
  "| One connection among same type | — | `airweave_system_metadata.sync_id` |",
].join("\n");
const DEFAULT_CACHE_TTL_MS = 120_000;
const SOURCE_LIST_CACHE_TTL_MS = Number.parseInt(
  process.env.MUSA_SOURCE_LIST_CACHE_TTL_MS || "",
  10
) || DEFAULT_CACHE_TTL_MS;
const SOURCE_TYPE_CACHE_TTL_MS = 600_000;

/** @type {Map<string, { at: number, rows: object[] }>} */
const sourceListCache = new Map();
/** @type {Map<string, { at: number, description: string | null }>} */
const sourceTypeDescriptionCache = new Map();

const SAFE_CONFIG_KEYS = new Set([
  "branch",
  "repo_name",
  "repository",
  "path",
  "root_path",
  "base_path",
  "project",
  "workspace",
  "folder",
  "directory",
  "url",
  "base_url",
  "site_url",
  "space_key",
  "project_key",
]);

// ── Filter schemas ───────────────────────────────────────────────────────────
const filterConditionSchema = z.object({
  field: z.string().describe(
    "Field to filter on. IMPORTANT: airweave_system_metadata.source_name is the source TYPE " +
    "(short_name, e.g. github), NOT the connection display name (e.g. torch_musa). " +
    "Other options: entity_id, name, created_at, updated_at, breadcrumbs.*, " +
    "airweave_system_metadata.entity_type, airweave_system_metadata.sync_id, " +
    "airweave_system_metadata.original_entity_id, airweave_system_metadata.chunk_index, " +
    "airweave_system_metadata.sync_job_id"
  ),
  operator: z.enum([
    "equals", "not_equals", "contains",
    "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal",
    "in", "not_in"
  ]).describe("Comparison operator"),
  value: z.union([
    z.string(), z.number(), z.boolean(),
    z.array(z.string()), z.array(z.number())
  ]).describe("Value to compare against. Use a list for 'in'/'not_in'"),
});

const filterGroupSchema = z.object({
  conditions: z.array(filterConditionSchema).min(1)
    .describe("Conditions within this group (combined with AND)"),
});

// ── Configuration ────────────────────────────────────────────────────────────
function loadConfig() {
  const apiKey = process.env.AIRWEAVE_API_KEY;
  const collection = process.env.AIRWEAVE_COLLECTION;
  const baseUrl = (process.env.AIRWEAVE_BASE_URL || DEFAULT_BASE_URL).replace(/\/$/, "");
  const organizationId = process.env.AIRWEAVE_ORGANIZATION_ID || "";

  if (!apiKey) {
    console.error("Error: AIRWEAVE_API_KEY environment variable is required");
    process.exit(1);
  }
  if (!collection) {
    console.error("Error: AIRWEAVE_COLLECTION environment variable is required");
    process.exit(1);
  }

  return { apiKey, collection, baseUrl, organizationId };
}

function buildAuthHeaders(config) {
  const headers = {
    "Content-Type": "application/json",
    "X-API-Key": config.apiKey,
    "X-Client-Name": "musa-knowledge-search",
    "X-Client-Version": VERSION,
  };
  if (config.organizationId) {
    headers["X-Organization-ID"] = config.organizationId;
  }
  return headers;
}

function listCacheKey(config, includeDetails) {
  const raw = `${config.apiKey}|${config.organizationId}|${config.collection}|details=${includeDetails}`;
  return createHash("sha256").update(raw).digest("hex").slice(0, 24);
}

function isSensitiveKey(key) {
  const lower = String(key).toLowerCase();
  return (
    lower.includes("password") ||
    lower.includes("secret") ||
    lower.includes("token") ||
    lower.includes("credential") ||
    lower.includes("api_key") ||
    lower.includes("apikey") ||
    lower.includes("private_key") ||
    lower.includes("client_secret")
  );
}

/** Extract only safe, non-sensitive config fields for agent context. */
function extractSafeConfig(config) {
  if (!config || typeof config !== "object" || Array.isArray(config)) {
    return {};
  }
  const out = {};
  for (const [key, value] of Object.entries(config)) {
    if (isSensitiveKey(key)) continue;
    if (!SAFE_CONFIG_KEYS.has(key)) continue;
    if (value === null || value === undefined) continue;
    if (typeof value === "object") continue;
    out[key] = String(value);
  }
  return out;
}

function formatBranch(safeConfig) {
  return safeConfig.branch || "-";
}

function escapeMarkdownCell(value) {
  return String(value ?? "-").replace(/\|/g, "\\|").replace(/\n/g, " ");
}

function buildFilterHint(shortName, syncId, duplicateTypeCount) {
  const parts = [
    `(type→source_name) airweave_system_metadata.source_name = "${shortName}"`,
  ];
  if (duplicateTypeCount > 1 && syncId) {
    parts.push(`airweave_system_metadata.sync_id = "${syncId}"`);
  }
  return parts.join("; ");
}

// ── Airweave API ─────────────────────────────────────────────────────────────
async function airweaveFetch(config, path, { query } = {}) {
  const url = new URL(`${config.baseUrl}${path.startsWith("/") ? path : `/${path}`}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const response = await fetch(url, {
    method: "GET",
    headers: buildAuthHeaders(config),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Airweave API error (${response.status}): ${response.statusText}\nBody: ${text}`);
  }

  return await response.json();
}

async function searchAirweave(config, tier, body) {
  const url = `${config.baseUrl}/collections/${config.collection}/search/${tier}`;
  const headers = buildAuthHeaders(config);

  console.error(
    `[search/${tier}] collection=${config.collection} baseUrl=${config.baseUrl} orgId=${config.organizationId || "none"}`
  );

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Airweave API error (${response.status}): ${response.statusText}\nBody: ${text}`);
  }

  return await response.json();
}

async function fetchAllSourceConnections(config) {
  const all = [];
  let skip = 0;
  const limit = 1000;

  while (true) {
    const batch = await airweaveFetch(config, "/source-connections", {
      query: { collection: config.collection, skip, limit },
    });
    if (!Array.isArray(batch)) {
      throw new Error("Unexpected source-connections list response (expected array)");
    }
    all.push(...batch);
    if (batch.length < limit) break;
    skip += limit;
  }

  return all;
}

async function fetchSourceConnectionDetail(config, connectionId) {
  return await airweaveFetch(config, `/source-connections/${connectionId}`);
}

async function fetchSourceTypeDescription(config, shortName) {
  const cacheKey = `${config.baseUrl}|${shortName}`;
  const cached = sourceTypeDescriptionCache.get(cacheKey);
  if (cached && Date.now() - cached.at < SOURCE_TYPE_CACHE_TTL_MS) {
    return cached.description;
  }

  try {
    const source = await airweaveFetch(config, `/sources/${shortName}`);
    const description = source?.description ? String(source.description) : null;
    sourceTypeDescriptionCache.set(cacheKey, { at: Date.now(), description });
    return description;
  } catch {
    sourceTypeDescriptionCache.set(cacheKey, { at: Date.now(), description: null });
    return null;
  }
}

/**
 * Build normalized source rows for a collection.
 * @returns {Promise<{ rows: object[], truncated: boolean, total: number }>}
 */
async function buildCollectionSourceRows(config, includeDetails) {
  const connections = await fetchAllSourceConnections(config);
  const typeCounts = new Map();
  for (const conn of connections) {
    const sn = conn.short_name || "unknown";
    typeCounts.set(sn, (typeCounts.get(sn) || 0) + 1);
  }

  const uniqueShortNames = [...new Set(connections.map((c) => c.short_name).filter(Boolean))];
  const typeDescriptions = new Map();
  await Promise.all(
    uniqueShortNames.map(async (shortName) => {
      typeDescriptions.set(shortName, await fetchSourceTypeDescription(config, shortName));
    })
  );

  const rows = [];
  for (const conn of connections) {
    const shortName = conn.short_name || "unknown";
    const duplicateTypeCount = typeCounts.get(shortName) || 1;

    let safeConfig = {};
    let connectionDescription = null;
    let syncId = conn.sync_id || null;
    let detailStatus = conn.status;

    if (includeDetails) {
      try {
        const detail = await fetchSourceConnectionDetail(config, conn.id);
        safeConfig = extractSafeConfig(detail.config);
        connectionDescription = detail.description ? String(detail.description) : null;
        syncId = detail.sync_id || syncId;
        detailStatus = detail.status ?? detailStatus;
      } catch (err) {
        console.error(`[list-collection-sources] detail fetch failed for ${conn.id}:`, err.message);
      }
    }

    const filterHint = buildFilterHint(shortName, syncId, duplicateTypeCount);

    rows.push({
      connection_id: conn.id,
      name: conn.name,
      short_name: shortName,
      type_description: typeDescriptions.get(shortName) ?? null,
      connection_description: connectionDescription,
      entity_count: conn.entity_count ?? 0,
      status: detailStatus ?? conn.status ?? "unknown",
      is_authenticated: conn.is_authenticated ?? false,
      federated_search: conn.federated_search ?? false,
      branch: formatBranch(safeConfig),
      safe_config: safeConfig,
      sync_id: syncId,
      source_type: shortName,
      filter_by_source_type: {
        field: "airweave_system_metadata.source_name",
        operator: "equals",
        value: shortName,
      },
      filter_hint: filterHint,
    });
  }

  return {
    rows,
    truncated: false,
    total: rows.length,
  };
}

async function getCollectionSourceRows(config, { includeDetails = false, refresh = false } = {}) {
  const key = listCacheKey(config, includeDetails);
  const cached = sourceListCache.get(key);

  if (!refresh && cached && Date.now() - cached.at < SOURCE_LIST_CACHE_TTL_MS) {
    return { ...cached.payload, stale: false, cached: true };
  }

  try {
    const payload = await buildCollectionSourceRows(config, includeDetails);
    sourceListCache.set(key, { at: Date.now(), payload });
    return { ...payload, stale: false, cached: false };
  } catch (error) {
    if (cached) {
      console.error("[list-collection-sources] API failed, returning stale cache:", error.message);
      return { ...cached.payload, stale: true, cached: true, error: error.message };
    }
    throw error;
  }
}

function formatSourcesMarkdown(collection, payload, { includeDetails, stale, cached }) {
  const lines = [
    `## Collection Sources: ${collection}`,
    "",
    `**Total connections:** ${payload.total}${payload.truncated ? " (truncated)" : ""}`,
  ];

  if (stale) {
    lines.push("", `> ⚠ Stale cache — latest API call failed. Showing last known data.`);
  } else if (cached) {
    lines.push("", `> Cached result (TTL ${Math.round(SOURCE_LIST_CACHE_TTL_MS / 1000)}s). Pass \`refresh: true\` to bypass.`);
  }

  lines.push(
    "",
    SOURCE_FIELD_GLOSSARY,
    "",
    "Column **Source** = connection display name. Column **Type** = connector short_name (use this value in `source_name` filters).",
    "",
    "| Source (connection) | Type (filter value) | Entities | Status | Auth | Branch | Filter Hint |",
    "|---|---|---:|---|---|---|---|",
  );

  for (const row of payload.rows) {
    lines.push(
      `| ${escapeMarkdownCell(row.name)} | ${escapeMarkdownCell(row.short_name)} | ${row.entity_count} | ` +
      `${escapeMarkdownCell(row.status)} | ${row.is_authenticated ? "yes" : "no"} | ` +
      `${escapeMarkdownCell(row.branch)} | ${escapeMarkdownCell(row.filter_hint)} |`
    );
  }

  if (includeDetails && payload.rows.length > 0) {
    lines.push("", "### Connection details", "");
    for (const row of payload.rows) {
      lines.push(`#### ${row.name} (\`${row.short_name}\`)`);
      if (row.connection_description) {
        lines.push(`- **Connection description:** ${row.connection_description}`);
      }
      if (row.type_description) {
        lines.push(`- **Source type:** ${row.type_description}`);
      }
      if (row.federated_search) {
        lines.push("- **Federated search:** yes (real-time API, not fully indexed)");
      }
      if (row.sync_id) {
        lines.push(`- **sync_id:** \`${row.sync_id}\``);
      }
      const configEntries = Object.entries(row.safe_config || {});
      if (configEntries.length > 0) {
        lines.push("- **Config (safe):** " + configEntries.map(([k, v]) => `${k}=${v}`).join(", "));
      }
      lines.push("");
    }
  }

  return lines.join("\n");
}

function formatSourcesJson(collection, payload, meta) {
  return JSON.stringify(
    {
      collection,
      ...meta,
      field_glossary: {
        connection_display_name: "Table column 'name' / Source — not indexed as source_name",
        source_type: "Connector short_name (e.g. github); filter via airweave_system_metadata.source_name",
        source_name_api_field: "Legacy API/index field name; holds source TYPE, not connection display name",
        per_connection: "When multiple connections share a type, also filter by airweave_system_metadata.sync_id",
      },
      sources: payload.rows,
    },
    null,
    2
  );
}

// ── Format Search Response ───────────────────────────────────────────────────
function formatSearchResponse(searchResponse, tier, collection) {
  const results = searchResponse.results ?? [];
  const formattedResults = results
    .map((result, index) => {
      const parts = [
        `**Result ${index + 1} (Score: ${result.relevance_score?.toFixed(3) || "N/A"}):**`,
      ];
      const source = result.airweave_system_metadata?.source_name;
      parts.push(source ? `${result.name || "unknown"} (${source})` : result.name || "unknown");
      if (result.breadcrumbs?.length > 0) {
        const trail = result.breadcrumbs.map((b) => b.name).join(" > ");
        parts.push(`📍 ${trail}`);
      }
      if (result.textual_representation) {
        parts.push(result.textual_representation);
      }
      if (result.web_url) {
        parts.push(`🔗 ${result.web_url}`);
      }
      return parts.join("\n");
    })
    .join("\n\n---\n\n");

  const summaryText = [
    `**Collection:** ${collection} | **Tier:** ${tier}`,
    `**Results:** ${results.length}`,
    "",
    formattedResults || "No results found.",
  ].join("\n");

  return {
    content: [{ type: "text", text: summaryText }],
  };
}

function formatErrorResponse(error, searchRequest, collection, baseUrl) {
  return {
    content: [
      {
        type: "text",
        text: [
          "**Error:** Failed to search collection.",
          "",
          `**Details:** ${error.message}`,
          "",
          "**Debugging Info:**",
          `- Collection: ${collection}`,
          `- Base URL: ${baseUrl}`,
          `- Parameters: ${JSON.stringify(searchRequest, null, 2)}`,
        ].join("\n"),
      },
    ],
  };
}

// ── Create MCP Server ────────────────────────────────────────────────────────
const config = loadConfig();
const server = new McpServer({
  name: "musa-knowledge-search",
  version: VERSION,
}, {
  capabilities: {
    tools: {},
    logging: {},
  },
});

const toolName = "musa_search";

const searchSchema = {
  query: z.string().min(1).max(1000)
    .describe("The search query text to find relevant documents and data"),
  tier: z.enum(["instant", "classic", "agentic"]).optional().default("classic")
    .describe(
      "Search tier: " +
      "'instant' (fastest, direct vector search), " +
      "'classic' (default, AI-optimized with LLM-planned strategy), " +
      "'agentic' (deepest, multi-step agent with tool calling)"
    ),
  retrieval_strategy: z.enum(["hybrid", "semantic", "keyword"]).optional()
    .describe("Only for instant tier. 'hybrid' (default), 'semantic', or 'keyword'"),
  limit: z.number().min(1).max(1000).optional().default(100)
    .describe("Maximum number of results to return"),
  offset: z.number().min(0).optional().default(0)
    .describe("Number of results to skip (instant and classic only)"),
  thinking: z.boolean().optional()
    .describe("Only for agentic tier. Enable extended thinking / chain-of-thought"),
  filter: z.array(filterGroupSchema).optional()
    .describe("Filter groups (combined with OR). Each group has conditions combined with AND"),
};

const searchDescription = [
  "Search the configured MUSA / Airweave collection.",
  "",
  "For broad semantic search, call this tool directly. " +
  "If you need source filters, entity counts, branches/repos, or don't know which connections exist, call `list-collection-sources` first (it includes filter hints and the source field glossary).",
  "",
  "Tiers: `instant` (~1s), `classic` (default, ~2-5s), `agentic` (~10-30s).",
  "",
  "Filters: use hints from `list-collection-sources`; see the `filter` parameter schema for field names.",
  "",
  "If the user-facing answer uses chunks from these results, end with a brief \"References\" list of only what you used (name/title; web_url when present). Otherwise omit.",
].join("\n");

server.tool(
  toolName,
  searchDescription,
  searchSchema,
  async (params) => {
    try {
      const tier = params.tier || "classic";
      const filter = params.filter;

      let response;
      switch (tier) {
        case "instant":
          response = await searchAirweave(config, "instant", {
            query: params.query,
            retrieval_strategy: params.retrieval_strategy,
            filter,
            limit: params.limit,
            offset: params.offset,
          });
          break;
        case "agentic":
          response = await searchAirweave(config, "agentic", {
            query: params.query,
            thinking: params.thinking,
            filter,
            limit: params.limit,
          });
          break;
        case "classic":
        default:
          response = await searchAirweave(config, "classic", {
            query: params.query,
            filter,
            limit: params.limit,
            offset: params.offset,
          });
          break;
      }

      return formatSearchResponse(response, tier, config.collection);
    } catch (error) {
      if (error instanceof z.ZodError) {
        const errorMessages = error.errors.map((e) => `${e.path.join(".")}: ${e.message}`);
        return {
          content: [
            {
              type: "text",
              text: `**Parameter Validation Errors:**\n${errorMessages.join("\n")}`,
            },
          ],
        };
      }
      console.error("Error in search tool:", error);
      return formatErrorResponse(error, params, config.collection, config.baseUrl);
    }
  }
);

const listSourcesSchema = {
  format: z.enum(["markdown", "json"]).optional().default("markdown")
    .describe("Output format: markdown (default, human-readable) or json (programmatic)"),
  includeDetails: z.boolean().optional().default(false)
    .describe("Fetch per-connection details (descriptions, safe config, sync_id). Slower; uses more API calls."),
  refresh: z.boolean().optional().default(false)
    .describe("Bypass cached source list and fetch fresh data from the API"),
};

const listSourcesDescription = [
  "List available sources in the configured collection, including connection names, source types, entity counts, " +
  "safe metadata (branch/repo when available), and filter hints for `musa_search`.",
  "",
  "Clarifies Airweave naming: column Source = connection display name; Type = connector short_name. " +
  "Filters must use Type (via API field `source_name`, legacy name) — never the Source column value unless you only mean sync_id. " +
  "JSON includes filter_by_source_type and field_glossary.",
].join("\n");

server.tool(
  "list-collection-sources",
  listSourcesDescription,
  listSourcesSchema,
  async (params) => {
    try {
      const format = params.format || "markdown";
      const includeDetails = params.includeDetails ?? false;
      const refresh = params.refresh ?? false;

      const result = await getCollectionSourceRows(config, { includeDetails, refresh });
      const meta = {
        stale: result.stale,
        cached: result.cached,
        truncated: result.truncated,
        total: result.total,
      };

      const text =
        format === "json"
          ? formatSourcesJson(config.collection, result, meta)
          : formatSourcesMarkdown(config.collection, result, {
            includeDetails,
            stale: result.stale,
            cached: result.cached,
          });

      return { content: [{ type: "text", text }] };
    } catch (error) {
      if (error instanceof z.ZodError) {
        const errorMessages = error.errors.map((e) => `${e.path.join(".")}: ${e.message}`);
        return {
          content: [
            {
              type: "text",
              text: `**Parameter Validation Errors:**\n${errorMessages.join("\n")}`,
            },
          ],
        };
      }
      console.error("Error in list-collection-sources:", error);
      return {
        content: [
          {
            type: "text",
            text: [
              "**Error:** Failed to list collection sources.",
              "",
              `**Details:** ${error.message}`,
              "",
              `- Collection: ${config.collection}`,
              `- Base URL: ${config.baseUrl}`,
            ].join("\n"),
          },
        ],
      };
    }
  }
);

server.tool(
  "get-config",
  "MUSA Knowledge Search MCP configuration and recommended tool workflow",
  {},
  async () => {
    return {
      content: [
        {
          type: "text",
          text: [
            "**MUSA Knowledge Search MCP**",
            "",
            `- **Collection:** ${config.collection}`,
            `- **Base URL:** ${config.baseUrl}`,
            `- **API Key:** ${config.apiKey ? "✓ Configured" : "✗ Missing"}`,
            `- **Organization ID:** ${config.organizationId || "Not set"}`,
            "",
            "**Recommended workflow:**",
            "- Use `list-collection-sources` before search when you need source-specific filters, source types, entity counts, branches, repos, or when you are unsure which sources exist.",
            "- If the source catalog is already known in the current conversation, search directly with `musa_search` and the appropriate filter.",
            "- For broad collection-wide semantic search, call `musa_search` directly.",
            "",
            "**Tools:**",
            "- `list-collection-sources` — source catalog and filter hints for search",
            `- \`${toolName}\` — search this collection`,
            "- `get-config` — this summary",
            "",
            "**Source naming (read before filtering):**",
            "- **Connection name** (e.g. torch_musa): shown as Source in the catalog — not stored in `source_name`.",
            "- **Source type** (e.g. github): filter with `airweave_system_metadata.source_name` (legacy API field name).",
            "- **One connection** when types duplicate: add `airweave_system_metadata.sync_id` from the catalog.",
          ].join("\n"),
        },
      ],
    };
  }
);

process.on("SIGINT", () => {
  console.error("Shutting down MUSA Knowledge Search MCP server...");
  process.exit(0);
});
process.on("SIGTERM", () => {
  console.error("Shutting down MUSA Knowledge Search MCP server...");
  process.exit(0);
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MUSA Knowledge Search MCP server started");
  console.error(`Collection: ${config.collection}`);
  console.error(`Base URL: ${config.baseUrl}`);
}

main().catch((error) => {
  console.error("Fatal error in MUSA Knowledge Search MCP server:", error);
  process.exit(1);
});
