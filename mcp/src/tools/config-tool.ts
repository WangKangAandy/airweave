// Configuration tool implementation

export function createConfigTool(toolName: string, collection: string, baseUrl: string, apiKey: string) {
    return {
        name: "get-config",
        description: "Get the current Airweave MCP server configuration",
        schema: {}, // Empty schema for no parameters
        handler: async () => {
            return {
                content: [
                    {
                        type: "text" as const,
                        text: [
                            "**Airweave MCP Server Configuration:**",
                            "",
                            `- **Collection ID:** ${collection}`,
                            `- **Base URL:** ${baseUrl}`,
                            `- **API Key:** ${apiKey ? "✓ Configured" : "✗ Missing"}`,
                            "",
                            "**Available Commands:**",
                            `- \`${toolName}\`: Search within the configured Airweave collection`,
                            "- `get-config`: Show this configuration information",
                        ].join("\n"),
                    },
                ],
            };
        }
    };
}
