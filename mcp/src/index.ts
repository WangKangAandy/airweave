#!/usr/bin/env node

// Main entry point for the Airweave MCP Search Server

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createMcpServer, validateEnvironment } from "./server.js";

// Validate environment variables and get configuration
const config = validateEnvironment();

// Create MCP server
const server = createMcpServer(config);

// Main function to start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr so it doesn't interfere with MCP protocol
  console.error("Airweave MCP Search Server started");
  console.error(`Collection: ${config.collection}`);
  console.error(`Base URL: ${config.baseUrl}`);
}

// Handle graceful shutdown
process.on("SIGINT", () => {
  console.error("Shutting down Airweave MCP server...");
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.error("Shutting down Airweave MCP server...");
  process.exit(0);
});

// Start the server
main().catch((error) => {
  console.error("Fatal error in Airweave MCP server:", error);
  process.exit(1);
});