# Confluence MCP Gateway Plan

## Background

Current Airweave source integrations are primarily sync-and-index flows (pull data, chunk, embed, store).
For Confluence in sensitive enterprise environments, full sync may be risky or undesirable.
The target mode is on-demand access: when an agent needs content, query Confluence through MCP in real time.

## Goal

Make Airweave a unified configuration and gateway layer for Confluence MCP, without deep business adaptation.

- Airweave UI stores Confluence connection settings (URL, auth type, PAT, policy).
- Airweave MCP exposes Confluence MCP tools to agents in near-native form.
- Airweave does not force full crawl or embedding for this mode.

## Non-Goals

- Re-implement all Confluence MCP tools as first-class Airweave domain APIs.
- Build a complex LLM planner inside Airweave to decide tool orchestration.
- Replace direct Confluence MCP behavior with custom semantic wrappers.

## High-Level Architecture

1. Agent connects to Airweave MCP.
2. Airweave MCP loads enabled upstream MCP connections from Airweave config.
3. Airweave MCP discovers upstream tools via MCP `tools/list`.
4. Airweave MCP re-publishes upstream tools (with namespace prefix) to agent.
5. Agent calls these proxied tools through Airweave MCP.
6. Airweave MCP forwards call to upstream MCP (`tools/call`) and returns response.

In this design, Airweave is the control plane and policy enforcement point, not a semantic tool translator.

## Why This Direction

- Preserves full Confluence MCP capability without one-by-one reimplementation.
- Keeps user experience centralized in Airweave configuration.
- Avoids forcing sync/embedding for sensitive internal knowledge.
- Reduces long-term maintenance compared with deep source-specific adapters.

## Proposed Configuration Model

Store a new "MCP upstream connection" resource in Airweave:

- `name`: friendly name
- `provider`: `confluence` / `atlassian`
- `mcp_server_url`: SSE endpoint
- `auth_type`: `pat` (extensible later)
- `credentials`: encrypted token material
- `headers_template`: optional header mapping
- `enabled`: boolean
- `tool_policy`:
  - `allowed_tools`: whitelist
  - `blocked_tools`: blacklist
  - `read_only_mode`: default true
  - `max_calls_per_minute`
  - `timeout_ms`
  - `max_payload_bytes`

## Tool Exposure Strategy

Use deterministic namespacing when re-publishing tools:

- Upstream tool: `confluence_search`
- Exposed by Airweave MCP: `atlassian.confluence_search` (example)

Benefits:

- Avoid name collisions with native Airweave MCP tools.
- Keep tool provenance visible to agent.
- Enable policy checks by namespace.

## Runtime Flow

### 1. MCP Server Startup / Session Init

- Load enabled upstream connections for current org/user scope.
- For each upstream:
  - establish MCP client session
  - call `tools/list`
  - cache tool descriptors with TTL
  - register proxied tool descriptors in Airweave MCP

### 2. Tool Call Handling

- Validate target proxied tool exists.
- Enforce org policy (`allowed_tools`, read-only guard, limits).
- Apply credential/header injection from Airweave secure config.
- Forward request to upstream MCP tool.
- Return upstream result as-is (plus optional metadata).

### 3. Observability

Log per call:

- org/user/source connection id
- tool name
- duration
- payload size
- success/failure class
- upstream error code

## Security and Governance Requirements

- Encrypt all PAT secrets at rest.
- Never expose raw secrets in MCP responses or logs.
- Default deny for mutation tools when `read_only_mode = true`.
- Validate tool args size and timeout to prevent abuse.
- Add per-org rate limiting to avoid accidental high-cost fanout.

## Compatibility with Existing Search

This gateway mode is independent from sync-index search.

- Existing vector search remains unchanged.
- MCP gateway tools are available for agent direct runtime calls.
- Optional future step: hybrid orchestration combining vector results and live MCP calls.

This keeps rollout low risk and avoids invasive changes to current search pipelines.

## Rollout Plan

### Phase 1 (MVP)

- Add Airweave config entity for upstream MCP connection.
- Implement one upstream: Atlassian MCP over SSE.
- Proxy `tools/list` and `tools/call` with namespaces.
- Enforce read-only + whitelist policy.

### Phase 2

- Add UI for connection testing and tool preview.
- Add per-tool policy controls in UI.
- Add audit trail page.

### Phase 3

- Support multiple upstream MCP providers (GitLab, internal docs, etc.).
- Add optional caching layer for frequently repeated queries.

## Open Questions

- Should tool visibility be scoped per collection or per organization?
- Should agents see all allowed tools or only context-selected subsets?
- Is response caching required for latency/cost, and what TTL is acceptable?
- Do we need policy templates (strict, balanced, full-access) out of the box?

## Decision Summary

Adopt a gateway model:

- Airweave handles configuration, policy, audit, and credential management.
- Airweave MCP dynamically proxies upstream Confluence MCP tools.
- Agent receives near-native MCP capability without Airweave deep tool-by-tool adaptation.
