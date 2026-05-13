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


@pytest.mark.asyncio
async def test_resolve_knowledge_base_space_links_as_space():
    """Knowledge-base/workspace style links should resolve as space entries."""
    resolver = DingTalkEntryResolver()
    raw = (
        "https://alidocs.dingtalk.com/spaces/By8jQS1ZYjGn5b0M "
        "https://example.com/path?workspaceId=work_123"
    )

    result = await resolver.resolve_many(raw)

    assert result.invalid_entries == []
    assert len(result.resolved_entries) == 2
    assert result.resolved_entries[0].entry_type == "space"
    assert result.resolved_entries[0].token == "By8jQS1ZYjGn5b0M"
    assert result.resolved_entries[1].entry_type == "space"
    assert result.resolved_entries[1].token == "work_123"
