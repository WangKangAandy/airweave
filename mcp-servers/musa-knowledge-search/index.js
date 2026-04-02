#!/usr/bin/env node
/**
 * Airweave Search MCP Server
 *
 * 照搬官方 airweave-mcp-search@0.9.60 实现
 * 使用 X-API-Key 认证（解决官方 Authorization: Bearer 认证 bug）
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const VERSION = "1.0.0";
const DEFAULT_BASE_URL = "https://api.airweave.ai";

// ── Filter schemas（照搬官方）──────────────────────────────────────────────
const filterConditionSchema = z.object({
  field: z.string().describe(
    "Field to filter on. Options: entity_id, name, created_at, updated_at, " +
    "breadcrumbs.entity_id, breadcrumbs.name, breadcrumbs.entity_type, " +
    "airweave_system_metadata.source_name, airweave_system_metadata.entity_type, " +
    "airweave_system_metadata.original_entity_id, airweave_system_metadata.chunk_index, " +
    "airweave_system_metadata.sync_id, airweave_system_metadata.sync_job_id"
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

// ── Configuration（照搬官方 + 保持 X-API-Key 认证）───────────────────────────
function loadConfig() {
  const apiKey = process.env.AIRWEAVE_API_KEY;
  const collection = process.env.AIRWEAVE_COLLECTION;
  const baseUrl = process.env.AIRWEAVE_BASE_URL || DEFAULT_BASE_URL;
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

// ── Airweave API Client（照搬官方 + 保持 X-API-Key 认证）─────────────────────
async function searchAirweave(config, tier, body) {
  const url = `${config.baseUrl}/collections/${config.collection}/search/${tier}`;

  const headers = {
    "Content-Type": "application/json",
    "X-API-Key": config.apiKey,  // 保持我们的认证方式（解决官方 bug）
    "X-Client-Name": "airweave-search-mcp",
    "X-Client-Version": VERSION,
  };

  if (config.organizationId) {
    headers["X-Organization-ID"] = config.organizationId;
  }

  console.error(`[search/${tier}] collection=${config.collection} baseUrl=${config.baseUrl} orgId=${config.organizationId || "none"}`);

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

// ── Format Search Response（照搬官方）────────────────────────────────────────
function formatSearchResponse(searchResponse, tier, collection) {
  const results = searchResponse.results ?? [];
  const formattedResults = results
    .map((result, index) => {
      const parts = [
        `**Result ${index + 1} (Score: ${result.relevance_score?.toFixed(3) || "N/A"}):**`,
      ];
      // Name + source
      const source = result.airweave_system_metadata?.source_name;
      parts.push(source ? `${result.name || "unknown"} (${source})` : result.name || "unknown");
      // Breadcrumbs
      if (result.breadcrumbs?.length > 0) {
        const trail = result.breadcrumbs.map((b) => b.name).join(" > ");
        parts.push(`📍 ${trail}`);
      }
      // Content - 核心改进！
      if (result.textual_representation) {
        parts.push(result.textual_representation);
      }
      // Link
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
    content: [
      {
        type: "text",
        text: summaryText,
      },
    ],
  };
}

// ── Format Error Response（照搬官方）─────────────────────────────────────────
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

// ── Create MCP Server（照搬官方）──────────────────────────────────────────────
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

// ── Search Tool（照搬官方）────────────────────────────────────────────────────
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
    .describe("Only for instant tier. 'hybrid' (default, semantic + keyword), 'semantic' (dense/neural only), 'keyword' (BM25 only)"),
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
  "Search the MUSA knowledge base across GitHub repos, official docs, Confluence pages, Jira issues, and more.",
  "",
  "This tool searches an Airweave collection that indexes MUSA-related resources:",
  "- **Code repos**: MUSA SDK, PyTorch-MUSA, MUSA examples and demos",
  "- **Documentation**: Official MUSA docs, API references, guides",
  "- **Confluence**: Internal wiki pages, design docs, meeting notes",
  "- **Jira**: MUSA-related issues, bug reports, feature requests",
  "",
  "Supports three search tiers:",
  "- `instant`: Fast vector search (~1s) — quick lookups",
  "- `classic` (default): AI-optimized search (~2-5s) — best for most queries",
  "- `agentic`: Multi-step agent (~10-30s) — complex analysis, summarization",
  "",
  "**Parameters:**",
  "- `query`: Search text",
  "- `tier`: instant | classic | agentic (default: classic)",
  "- `limit`: Max results (default: 100)",
  "- `filter`: Narrow by source, e.g. filter by source_name='github'",
  "",
  "**Examples:**",
  "- `{'query': 'torch.musa.is_available()'}` — Find API usage examples",
  "- `{'query': 'MUSA driver installation', 'tier': 'agentic'}` — Deep search guides",
  "- `{'query': 'JIRA-123', 'tier': 'instant'}` — Quick issue lookup",
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

// ── Config Tool（照搬官方）────────────────────────────────────────────────────
server.tool(
  "get-config",
  "Get the current Airweave MCP server configuration",
  {},
  async () => {
    return {
      content: [
        {
          type: "text",
          text: [
            "**Airweave MCP Server Configuration:**",
            "",
            `- **Collection ID:** ${config.collection}`,
            `- **Base URL:** ${config.baseUrl}`,
            `- **API Key:** ${config.apiKey ? "✓ Configured" : "✗ Missing"}`,
            `- **Organization ID:** ${config.organizationId || "Not set"}`,
            "",
            "**Available Commands:**",
            `- \`${toolName}\`: Search within the configured Airweave collection`,
            "- `get-config`: Show this configuration information",
          ].join("\n"),
        },
      ],
    };
  }
);

// ── Graceful Shutdown（照搬官方）──────────────────────────────────────────────
process.on("SIGINT", () => {
  console.error("Shutting down Airweave MCP server...");
  process.exit(0);
});
process.on("SIGTERM", () => {
  console.error("Shutting down Airweave MCP server...");
  process.exit(0);
});

// ── Main Entry（照搬官方）──────────────────────────────────────────────────────
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Airweave MCP Search Server started");
  console.error(`Collection: ${config.collection}`);
  console.error(`Base URL: ${config.baseUrl}`);
}

main().catch((error) => {
  console.error("Fatal error in Airweave MCP server:", error);
  process.exit(1);
});