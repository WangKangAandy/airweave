"""Unit tests for Dingtalk source behavior."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.configs.config import DingtalkConfig
from airweave.platform.sources.dingtalk_docs import DingtalkSource
from airweave.platform.sources.resolvers.base import BatchResolveResult
from airweave.platform.sources.resolvers.dingtalk import ResolvedDingTalkEntry


def _mock_auth(token: str = "token"):
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value=token)
    auth.force_refresh = AsyncMock(return_value="refreshed")
    auth.supports_refresh = True
    auth.provider_kind = "oauth"
    return auth


def _mock_logger():
    return MagicMock()


def _mock_http_client():
    return AsyncMock()


async def _make_source(config: DingtalkConfig) -> DingtalkSource:
    return await DingtalkSource.create(
        auth=_mock_auth(),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=config,
    )


@pytest.mark.asyncio
async def test_resolve_primary_entries_prefers_links():
    """links should be preferred over root IDs when both are present."""
    config = DingtalkConfig(
        links="doc:from-link",
        root_space_id="space-ignored",
        operator_union_id="operator-1",
    )
    source = await _make_source(config)

    with patch.object(
        source.entry_resolver,
        "resolve_many",
        new_callable=AsyncMock,
        return_value=BatchResolveResult(
            resolved_entries=[ResolvedDingTalkEntry("doc", "from-link", "doc:from-link")],
            invalid_entries=[],
        ),
    ):
        entries = await source._resolve_primary_entries()

    assert len(entries) == 1
    assert entries[0].entry_type == "doc"
    assert entries[0].token == "from-link"


@pytest.mark.asyncio
async def test_generate_entities_marks_unsupported_when_all_content_paths_empty():
    """unsupported status is emitted when block/direct/fallback all yield empty."""
    config = DingtalkConfig(root_space_id="space-1", operator_union_id="operator-1")
    source = await _make_source(config)

    async def _discover():
        yield {"id": "doc-1", "title": "Doc 1"}

    with patch.object(source, "_get_access_token", new_callable=AsyncMock, return_value="token"), patch.object(
        source,
        "_resolve_primary_entries",
        new_callable=AsyncMock,
        return_value=[ResolvedDingTalkEntry("doc", "doc-1", "doc:doc-1")],
    ), patch.object(
        source,
        "_discover_docs",
        side_effect=lambda **kwargs: _discover(),
    ), patch.object(
        source,
        "_extract_doc_content",
        new_callable=AsyncMock,
        return_value=("", "empty", False),
    ), patch.object(
        source,
        "_extract_doc_content_direct_api",
        new_callable=AsyncMock,
        return_value=("", "empty"),
    ), patch.object(
        source,
        "_extract_doc_content_fallback",
        new_callable=AsyncMock,
        return_value=("", "unsupported"),
    ):
        entities = []
        async for entity in source.generate_entities():
            entities.append(entity)

    assert len(entities) == 1
    assert entities[0].content_source == "fallback"
    assert entities[0].content_status == "unsupported"


@pytest.mark.asyncio
async def test_generate_entities_prefers_direct_api_when_block_tree_empty():
    """direct_api path should be used when block tree has no content."""
    config = DingtalkConfig(root_space_id="space-1", operator_union_id="operator-1")
    source = await _make_source(config)

    async def _discover():
        yield {"id": "doc-2", "title": "Doc 2"}

    with patch.object(source, "_get_access_token", new_callable=AsyncMock, return_value="token"), patch.object(
        source,
        "_resolve_primary_entries",
        new_callable=AsyncMock,
        return_value=[ResolvedDingTalkEntry("doc", "doc-2", "doc:doc-2")],
    ), patch.object(
        source,
        "_discover_docs",
        side_effect=lambda **kwargs: _discover(),
    ), patch.object(
        source,
        "_extract_doc_content",
        new_callable=AsyncMock,
        return_value=("", "empty", True),
    ), patch.object(
        source,
        "_extract_doc_content_direct_api",
        new_callable=AsyncMock,
        return_value=("direct content", "success"),
    ):
        entities = []
        async for entity in source.generate_entities():
            entities.append(entity)

    assert len(entities) == 1
    assert entities[0].content_source == "direct_api"
    assert entities[0].content_status == "success"
    assert entities[0].raw_content == "direct content"


@pytest.mark.asyncio
async def test_probe_scope_uses_wiki_query_for_http_links():
    """HTTP links should be probed through wiki queryByUrl instead of docs blocks."""
    config = DingtalkConfig(
        links="https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
        operator_union_id="operator-1",
    )
    source = await _make_source(config)
    entry = ResolvedDingTalkEntry(
        "doc",
        "MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
        "https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb?utm_scene=person_space",
    )

    with patch.object(source, "_post", new_callable=AsyncMock, return_value={"nodeId": "n1"}) as m_post, patch.object(
        source,
        "_get",
        new_callable=AsyncMock,
    ) as m_get:
        await source._probe_scope(entry=entry, access_token="token")

    m_post.assert_awaited_once()
    m_get.assert_not_called()


@pytest.mark.asyncio
async def test_probe_scope_requires_operator_union_id_for_http_links():
    """HTTP link probing should require operator_union_id."""
    config = DingtalkConfig(
        links="https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
        operator_union_id="",
    )
    source = await _make_source(config)
    entry = ResolvedDingTalkEntry(
        "doc",
        "MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
        "https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
    )

    with pytest.raises(ValueError, match="operator_union_id is required"):
        await source._probe_scope(entry=entry, access_token="token")


@pytest.mark.asyncio
async def test_generate_entities_http_doc_uses_download_info_content_flow():
    """HTTP docs should use official downloadInfo flow and persist real content."""
    config = DingtalkConfig(
        links="https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
        operator_union_id="operator-1",
    )
    source = await _make_source(config)

    async def _discover():
        yield {
            "id": "MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
            "title": "",
            "url": "",
            "source": "https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
        }

    with patch.object(source, "_get_access_token", new_callable=AsyncMock, return_value="token"), patch.object(
        source,
        "_resolve_primary_entries",
        new_callable=AsyncMock,
        return_value=[ResolvedDingTalkEntry("doc", "MyQA2dXW7edN241muMpLAmNPJzlwrZgb", "https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb")],
    ), patch.object(
        source,
        "_discover_docs",
        side_effect=lambda **kwargs: _discover(),
    ), patch.object(
        source,
        "_query_node_by_url",
        new_callable=AsyncMock,
        return_value={
            "nodeId": "MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
            "name": "python.adoc",
            "url": "https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb",
            "workspaceId": "space-1",
        },
    ) as m_query, patch.object(
        source,
        "_extract_http_doc_content",
        new_callable=AsyncMock,
        return_value=("我是猪", "success"),
    ) as m_http_extract, patch.object(
        source,
        "_extract_doc_content",
        new_callable=AsyncMock,
    ) as m_extract:
        entities = []
        async for entity in source.generate_entities():
            entities.append(entity)

    m_query.assert_awaited_once()
    m_http_extract.assert_awaited_once()
    m_extract.assert_not_called()
    assert len(entities) == 1
    assert entities[0].title == "python.adoc"
    assert entities[0].raw_content == "我是猪"
    assert entities[0].content_source == "download_info"
    assert entities[0].content_status == "success"

