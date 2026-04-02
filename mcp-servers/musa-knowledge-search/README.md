# MUSA Knowledge Search MCP Server

MCP server to search the MUSA knowledge base across GitHub, GitLab, Jira, Confluence, and official documentation.

## Features

- Search across multiple MUSA-related data sources in a single query
- Three search tiers for different depth and speed requirements:
  - `instant`: Fast vector search (~1s) — quick lookups
  - `classic`: AI-optimized search (~2-5s) — best for most queries (default)
  - `agentic`: Multi-step agent (~10-30s) — complex analysis, summarization
- Structured filtering by source, date, etc.

## Data Sources

The MUSA knowledge base indexes:

- **Code repos**: MUSA SDK, PyTorch-MUSA, MUSA examples and demos
- **Documentation**: Official MUSA docs, API references, guides
- **Confluence**: Internal wiki pages, design docs, meeting notes
- **Jira**: MUSA-related issues, bug reports, feature requests

## Installation

```bash
npx musa-knowledge-search
```

## Configuration

Add to your MCP client configuration (e.g., Claude Desktop, Cursor, OpenClaw):

```json
{
  "mcpServers": {
    "musa-knowledge-search": {
      "command": "npx",
      "args": ["-y", "musa-knowledge-search"],
      "env": {
        "AIRWEAVE_API_KEY": "your-api-key",
        "AIRWEAVE_COLLECTION": "your-collection-id"
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AIRWEAVE_API_KEY` | Yes | Airweave API key |
| `AIRWEAVE_COLLECTION` | Yes | Collection readable ID |
| `AIRWEAVE_BASE_URL` | No | API base URL (default: https://api.airweave.ai) |
| `AIRWEAVE_ORGANIZATION_ID` | No | Organization ID for multi-tenant |

## Tool: `musa_search`

Search the MUSA knowledge base.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Search query text |
| `tier` | enum | classic | instant / classic / agentic |
| `limit` | number | 100 | Max results (1-1000) |
| `offset` | number | 0 | Skip results for pagination |
| `retrieval_strategy` | enum | hybrid | hybrid / semantic / keyword (instant tier only) |
| `thinking` | boolean | false | Enable chain-of-thought (agentic tier only) |
| `filter` | array | - | Structured filters |

**Examples:**

```javascript
// Basic search
{ "query": "torch.musa.is_available()" }

// Deep search with agentic tier
{ "query": "MUSA driver installation guide", "tier": "agentic" }

// Quick lookup
{ "query": "JIRA-123", "tier": "instant" }

// Filter by source
{
  "query": "memory leak",
  "filter": [{
    "conditions": [{
      "field": "airweave_system_metadata.source_name",
      "operator": "equals",
      "value": "github"
    }]
  }]
}
```

## License

MIT