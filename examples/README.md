# Developer Enablement Materials

This folder contains educational materials and tutorials to help developers get started with Airweave quickly and effectively.

## Contents

### `quickstart_tutorial.py`
A comprehensive Python script that walks through the complete Airweave quickstart process:

1. **Deployment Setup** - Information about hosted vs self-hosted options
2. **Client Configuration** - Setting up the Airweave SDK
3. **Collection Creation** - Creating your first searchable collection
4. **Source Connections** - Adding data sources to your collection
5. **Basic Search** - Performing your first search queries
6. **Advanced Search** - Using filters, AI reranking, and other advanced features

## Usage

### Prerequisites
- Python 3.11+
- Airweave SDK: `pip install airweave-sdk`
- Valid Airweave API key (obtainable from Airweave dashboard)

### Running the Tutorial

#### Option 1: Environment Variable
```bash
export AIRWEAVE_API_KEY="your-api-key-here"
python quickstart_tutorial.py
```

#### Option 2: Interactive Input
```bash
python quickstart_tutorial.py
# Enter your API key when prompted
```

#### Option 3: Self-Hosted Instance
```bash
export AIRWEAVE_API_KEY="your-api-key-here"
export AIRWEAVE_BASE_URL="http://localhost:8001"
python quickstart_tutorial.py
```

## What You'll Learn

- How to create and manage collections
- How to connect data sources (Stripe, GitHub, Notion, etc.)
- Basic and advanced search techniques
- Filtering and query optimization
- AI-powered search features
- Best practices for data synchronization

## Next Steps

After completing the tutorial:

1. **Explore Connectors** - Try connecting different data sources
2. **Advanced Features** - Experiment with filters, AI reranking, and query interpretation
3. **MCP Integration** - Set up the MCP server for AI agent integration
4. **Production Setup** - Learn about organization management and scaling

## Resources

- [Full Documentation](https://docs.airweave.ai)
- [API Reference](https://docs.airweave.ai/api-reference)
- [Discord Server](https://discord.gg/484HY9Ehxt)
- [GitHub Repository](https://github.com/airweave-ai/airweave)

## Support

Need help? Contact us at hello@airweave.ai or join our Discord community!
