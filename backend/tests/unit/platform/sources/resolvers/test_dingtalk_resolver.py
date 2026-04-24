"""Unit tests for DingTalk entry resolver."""

import pytest

from airweave.platform.sources.resolvers.dingtalk import DingTalkEntryResolver


@pytest.mark.asyncio
async def test_resolve_nodes_link_as_doc():
    """`/i/nodes/<id>` links should resolve as doc entries."""
    resolver = DingTalkEntryResolver()
    raw = "https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPjzIwrZ"

    result = await resolver.resolve_many(raw)

    assert result.invalid_entries == []
    assert len(result.resolved_entries) == 1
    resolved = result.resolved_entries[0]
    assert resolved.entry_type == "doc"
    assert resolved.token == "MyQA2dXW7edN241muMpLAmNPjzIwrZ"
