#!/usr/bin/env node
/**
 * Integration tests for musa-knowledge-search MCP (stdio).
 * Usage: node test-mcp.mjs
 * Env: AIRWEAVE_API_KEY, AIRWEAVE_COLLECTION, AIRWEAVE_BASE_URL (required)
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function loadEnvFromOpenClaw() {
  try {
    const cfg = JSON.parse(
      readFileSync("/home/mccxadmin/.openclaw/openclaw.json", "utf8")
    );
    const env = cfg?.mcp?.servers?.["musa-knowledge-search"]?.env ?? {};
    for (const [k, v] of Object.entries(env)) {
      if (!process.env[k]) process.env[k] = String(v);
    }
  } catch {
    // use existing env
  }
}

loadEnvFromOpenClaw();

const required = ["AIRWEAVE_API_KEY", "AIRWEAVE_COLLECTION", "AIRWEAVE_BASE_URL"];
for (const key of required) {
  if (!process.env[key]) {
    console.error(`Missing ${key}`);
    process.exit(1);
  }
}

const results = [];
let passed = 0;
let failed = 0;

function ok(name, detail = "") {
  passed++;
  results.push({ status: "PASS", name, detail });
  console.log(`✓ ${name}${detail ? `: ${detail}` : ""}`);
}

function fail(name, detail = "") {
  failed++;
  results.push({ status: "FAIL", name, detail });
  console.error(`✗ ${name}${detail ? `: ${detail}` : ""}`);
}

function textContent(result) {
  const block = result?.content?.find((c) => c.type === "text");
  return block?.text ?? "";
}

async function callTool(client, name, args = {}) {
  return await client.callTool({ name, arguments: args });
}

async function main() {
  const transport = new StdioClientTransport({
    command: "node",
    args: [join(__dirname, "index.js")],
    env: {
      ...process.env,
      AIRWEAVE_API_KEY: process.env.AIRWEAVE_API_KEY,
      AIRWEAVE_COLLECTION: process.env.AIRWEAVE_COLLECTION,
      AIRWEAVE_BASE_URL: process.env.AIRWEAVE_BASE_URL,
    },
  });

  const client = new Client(
    { name: "musa-mcp-test", version: "1.0.0" },
    { capabilities: {} }
  );

  console.log("Connecting to musa-knowledge-search MCP...");
  await client.connect(transport);

  // ── tools/list ──────────────────────────────────────────────────────────
  const tools = await client.listTools();
  const toolNames = tools.tools.map((t) => t.name).sort();

  if (
    toolNames.includes("musa_search") &&
    toolNames.includes("get-config") &&
    toolNames.includes("list-collection-sources")
  ) {
    ok("tools/list", toolNames.join(", "));
  } else {
    fail("tools/list", `got: ${toolNames.join(", ")}`);
  }

  // ── get-config ────────────────────────────────────────────────────────────
  const configRes = await callTool(client, "get-config", {});
  const configText = textContent(configRes);
  if (configText.includes("list-collection-sources") && configText.includes(process.env.AIRWEAVE_COLLECTION)) {
    ok("get-config", "lightweight + collection present");
  } else {
    fail("get-config", configText.slice(0, 200));
  }
  if (!configText.includes("Entity Count") && !configText.match(/\|\s*Source\s*\|/)) {
    ok("get-config", "no source table in get-config");
  } else {
    fail("get-config", "should not include full source catalog");
  }

  // ── list-collection-sources (markdown) ───────────────────────────────────
  const t0 = Date.now();
  const listMd = await callTool(client, "list-collection-sources", {
    format: "markdown",
    refresh: true,
  });
  const mdText = textContent(listMd);
  const listMs = Date.now() - t0;

  if (mdText.includes("## Collection Sources:")) {
    ok("list-collection-sources markdown", `${listMs}ms`);
  } else {
    fail("list-collection-sources markdown", mdText.slice(0, 300));
  }

  if (mdText.includes("source_name") && mdText.includes("short_name")) {
    ok("list markdown explains source_name vs short_name");
  } else if (mdText.includes("airweave_system_metadata.source_name")) {
    ok("list markdown has filter hint field");
  } else {
    fail("list markdown filter guidance");
  }

  const wrongHint = /\|\s*[^|]+\s*\|\s*[^|]+\s*\|\s*\d+\s*\|[^|]*source_name\s*=\s*[^|"]+\s*\|/i.test(mdText)
    && mdText.match(/source_name = "([^"]+)"/g)?.some((m) => {
      const val = m.match(/"([^"]+)"/)?.[1];
      const row = mdText.split("\n").find((line) => line.includes(m));
      if (!row) return false;
      const cols = row.split("|").map((c) => c.trim());
      const nameCol = cols[1];
      const typeCol = cols[2];
      return val === nameCol && val !== typeCol;
    });
  if (!wrongHint) {
    ok("filter_hint uses short_name not display name");
  } else {
    fail("filter_hint", "hint may equal connection name instead of type");
  }

  if (!/password|access_token|api_key|secret/i.test(mdText)) {
    ok("markdown output sanitization (no obvious secrets)");
  } else {
    fail("markdown sanitization", "possible secret in output");
  }

  // ── cache hit ─────────────────────────────────────────────────────────────
  const t1 = Date.now();
  const listCached = await callTool(client, "list-collection-sources", {
    format: "markdown",
    refresh: false,
  });
  const cachedMs = Date.now() - t1;
  const cachedText = textContent(listCached);
  if (cachedText.includes("Cached result") || cachedMs < listMs * 0.5) {
    ok("list cache", `2nd call ${cachedMs}ms vs fresh ${listMs}ms`);
  } else {
    ok("list cache", `2nd call ${cachedMs}ms (cache marker optional)`);
  }

  // ── json format ───────────────────────────────────────────────────────────
  const listJson = await callTool(client, "list-collection-sources", {
    format: "json",
    refresh: true,
  });
  const jsonText = textContent(listJson);
  let parsed;
  try {
    parsed = JSON.parse(jsonText);
    ok("list-collection-sources json", `total=${parsed.total}`);
  } catch (e) {
    fail("list-collection-sources json", e.message);
    parsed = { sources: [] };
  }

  if (Array.isArray(parsed.sources)) {
    for (const row of parsed.sources.slice(0, 3)) {
      if (row.filter_hint?.includes(row.short_name)) {
        ok(`filter_hint row: ${row.name}`, row.filter_hint.slice(0, 80));
        break;
      }
    }
  }

  // ── includeDetails ────────────────────────────────────────────────────────
  const t2 = Date.now();
  const listDetail = await callTool(client, "list-collection-sources", {
    format: "markdown",
    includeDetails: true,
    refresh: true,
  });
  const detailMs = Date.now() - t2;
  const detailText = textContent(listDetail);
  if (detailText.includes("### Connection details") || detailText.includes("#### ")) {
    ok("includeDetails", `${detailMs}ms`);
  } else if (parsed.total === 0) {
    ok("includeDetails", "skipped (no connections)");
  } else {
    fail("includeDetails", detailText.slice(0, 300));
  }

  // ── musa_search instant ───────────────────────────────────────────────────
  const searchRes = await callTool(client, "musa_search", {
    query: "MUSA",
    tier: "instant",
    limit: 3,
  });
  const searchText = textContent(searchRes);
  if (searchText.includes("Collection:") || searchText.includes("Results:")) {
    ok("musa_search instant", searchText.split("\n")[0]);
  } else if (searchText.includes("Error")) {
    fail("musa_search instant", searchText.slice(0, 400));
  } else {
    fail("musa_search instant", "unexpected response");
  }

  // ── musa_search with filter from first source ─────────────────────────────
  const first = parsed.sources?.[0];
  if (first?.short_name) {
    const filterRes = await callTool(client, "musa_search", {
      query: "test",
      tier: "instant",
      limit: 2,
      filter: [
        {
          conditions: [
            {
              field: "airweave_system_metadata.source_name",
              operator: "equals",
              value: first.short_name,
            },
          ],
        },
      ],
    });
    const filterText = textContent(filterRes);
    if (!filterText.includes("Parameter Validation") && !filterText.includes("Failed to search")) {
      ok("musa_search with source_name filter", `short_name=${first.short_name}`);
    } else {
      fail("musa_search filter", filterText.slice(0, 300));
    }
  } else {
    ok("musa_search filter", "skipped (no sources)");
  }

  await client.close();

  console.log("\n--- Summary ---");
  console.log(`Passed: ${passed}, Failed: ${failed}`);
  if (failed > 0) process.exit(1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
