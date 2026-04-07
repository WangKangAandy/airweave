#!/usr/bin/env python3
"""
Airweave Quickstart Tutorial
============================

A simple walkthrough of the Airweave quickstart process:
1. Set up client
2. Create a collection
3. Add source connections
4. Search your collection
"""

import os
import asyncio
from airweave import AirweaveSDK

print("🎯 Airweave Quickstart Tutorial")
print("=" * 40)
print()

# =============================================================================
# Step 1: Choose deployment and set up client
# =============================================================================
print("🚀 Step 1: Set up Client")
print()
print("Deployment options:")
print("• Cloud Platform: https://app.airweave.ai (hosted service)")
print("• Self-Hosted: ./start.sh (local development)")
print()

# Get API key from environment or user input
api_key = os.getenv("AIRWEAVE_API_KEY")
if not api_key:
    api_key = input("Enter your Airweave API key: ").strip()

if not api_key:
    print("❌ API key required. Get one from https://app.airweave.ai")
    exit(1)

# Initialize client (change base_url for self-hosted)
base_url = os.getenv("AIRWEAVE_BASE_URL", "https://api.airweave.ai")
client = AirweaveSDK(api_key=api_key, base_url=base_url)

print(f"✅ Client initialized ({base_url})")
print()

# =============================================================================
# Step 2: Create a collection
# =============================================================================
print("📚 Step 2: Create a Collection")
print()
print("A collection is a group of different data sources that you can search using a single endpoint.")
print()

# Create collection
collection = client.collections.create(name="My First Collection")
collection_id = collection.readable_id

print(f"✅ Created collection: My First Collection")
print(f"📋 Collection ID: {collection_id}")
print()

# =============================================================================
# Step 3: Add source connection(s) to your collection
# =============================================================================
print("🔌 Step 3: Add Source Connection")
print()
print("A source connection is an authenticated link to a data source that automatically")
print("syncs data into your collection.")
print()

# Add a source connection (using Stripe as example)
# Replace with your actual API key for the source
source_connection = client.source_connections.create(
    name="My Stripe Connection",
    short_name="stripe",  # Available sources: stripe, github, notion, slack, etc.
    readable_collection_id=collection_id,
    authentication={
        "credentials": {
            "api_key": "SK_TEST_YOUR_STRIPE_API_KEY"  # Replace with real API key
        }
    }
)

print(f"✅ Created source connection: My Stripe Connection")
print(f"📊 Status: {source_connection.status}")
print(f"💡 Sync will start automatically - monitor progress in dashboard")
print()

# =============================================================================
# Step 4: Search your collection
# =============================================================================
print("🔍 Step 4: Search Your Collection")
print()
print("Once data is synced, you can search across all connected sources!")
print()

# Basic search
query = "Find returned payments from user John Doe?"
print(f"🔎 Searching for: '{query}'")
print()

try:
    results = client.collections.search(
        readable_id=collection_id,
        query=query
    )

    print(f"📊 Found {len(results.results)} results")
    print()

    # Show first few results
    for i, result in enumerate(results.results[:3], 1):
        print(f"Result {i}:")
        print(f"  📄 Content: {result['payload']['md_content'][:100]}...")
        print(f"  🏷️  Source: {result['payload']['source_name']}")
        print(f"  🎯 Score: {result['score']:.3f}")
        print()

    if len(results.results) > 3:
        print(f"... and {len(results.results) - 3} more results")
        print()

except Exception as e:
    print(f"⚠️  No results yet: {e}")
    print("💡 This is normal - data sync takes time. Try again in a few minutes.")
    print()

# =============================================================================
# Step 5: Advanced search example
# =============================================================================
print("⚡ Step 5: Advanced Search")
print()
print("Airweave supports filters, AI reranking, and more advanced features:")
print()

# Advanced search with filters
try:
    # Import search request schema from the SDK
    from airweave import SearchRequest, Filter, FieldCondition, MatchAny

    # Create advanced search request
    search_request = SearchRequest(
        query="customer feedback about pricing",
        filter=Filter(
            must=[
                FieldCondition(
                    key="source_name",
                    match=MatchAny(any=["Stripe", "Zendesk", "Slack"])
                )
            ]
        ),
        recency_bias=0.5,        # Prefer newer content
        score_threshold=0.7,     # High-quality results only
        enable_reranking=True,   # AI reranking for better relevance
        limit=10
    )

    advanced_results = client.collections.search_advanced(
        readable_id=collection_id,
        search_request=search_request
    )

    print(f"📊 Advanced search found {len(advanced_results.results)} results")
    print("✅ Used: filters + recency bias + score threshold + AI reranking")
    print()

except Exception as e:
    print(f"⚠️  Advanced search: {e}")
    print("💡 Normal if you don't have data from those specific sources yet")
    print()

# =============================================================================
# Tutorial complete!
# =============================================================================
print("🎉 Tutorial Complete!")
print("=" * 40)
print()
print("Next steps:")
print("• Add more source connections (GitHub, Notion, Slack, etc.)")
print("• Explore different search parameters and filters")
print("• Set up MCP server for AI agent integration")
print("• Check out the documentation: https://docs.airweave.ai")
print()
print("Need help? Join our Discord: https://discord.gg/484HY9Ehxt")
