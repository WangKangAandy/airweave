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
async def test_extract_doc_id_prefers_doc_key_before_dentry_uuid():
    """docKey should be preferred for docs APIs over dentryUuid."""
    source = await _make_source(DingtalkConfig(root_space_id="space-1", operator_union_id="operator-1"))
    item = {
        "dentryUuid": "uuid-1",
        "docKey": "doc-key-1",
        "dentryId": "dentry-id-1",
    }
    assert source._extract_doc_id(item) == "doc-key-1"
    assert source._candidate_doc_ids(item)[:3] == ["doc-key-1", "dentry-id-1", "uuid-1"]


@pytest.mark.asyncio
async def test_extract_item_type_uses_dentry_type():
    """dentryType should drive folder/doc classification for directory API results."""
    source = await _make_source(DingtalkConfig(root_space_id="space-1", operator_union_id="operator-1"))
    folder_item = {"dentryType": "folder"}
    file_item = {"dentryType": "file"}
    assert source._is_folder_type(folder_item) is True
    assert source._is_doc_type(folder_item) is False
    assert source._is_doc_type(file_item) is True


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
async def test_generate_entities_retries_content_with_candidate_doc_ids():
    """When first id fails, content extraction should retry other candidate ids."""
    config = DingtalkConfig(root_space_id="space-1", operator_union_id="operator-1")
    source = await _make_source(config)

    async def _discover():
        yield {"dentryUuid": "uuid-doc", "docKey": "doc-key-ok", "name": "Doc 1"}

    async def _extract_side_effect(*, doc_id: str, access_token: str):
        if doc_id == "uuid-doc":
            raise RuntimeError("invalid id path")
        if doc_id == "doc-key-ok":
            return ("hello from doc key", "success", True)
        return ("", "empty", False)

    with patch.object(source, "_get_access_token", new_callable=AsyncMock, return_value="token"), patch.object(
        source,
        "_resolve_primary_entries",
        new_callable=AsyncMock,
        return_value=[ResolvedDingTalkEntry("doc", "uuid-doc", "doc:uuid-doc")],
    ), patch.object(
        source,
        "_discover_docs",
        side_effect=lambda **kwargs: _discover(),
    ), patch.object(
        source,
        "_extract_doc_content",
        side_effect=_extract_side_effect,
    ) as m_extract:
        entities = []
        async for entity in source.generate_entities():
            entities.append(entity)

    assert len(entities) == 1
    assert entities[0].raw_content == "hello from doc key"
    assert entities[0].content_status == "success"
    called_ids = [call.kwargs["doc_id"] for call in m_extract.await_args_list]
    assert called_ids == ["doc-key-ok"]


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
async def test_probe_scope_folder_http_links_probe_directory_permission():
    """Folder links should additionally probe directory-list permission."""
    config = DingtalkConfig(
        links="https://alidocs.dingtalk.com/i/nodes/vNG4YZ7JnpM5MZkPuZ9zM0w9W2LD0oRE",
        operator_union_id="operator-1",
    )
    source = await _make_source(config)
    entry = ResolvedDingTalkEntry(
        "doc",
        "vNG4YZ7JnpM5MZkPuZ9zM0w9W2LD0oRE",
        "https://alidocs.dingtalk.com/i/nodes/vNG4YZ7JnpM5MZkPuZ9zM0w9W2LD0oRE",
    )

    async def _dirs():
        yield {"id": "child-1", "type": "doc"}

    with patch.object(
        source,
        "_post",
        new_callable=AsyncMock,
        return_value={
            "node": {
                "type": "FOLDER",
                "hasChildren": True,
                "workspaceId": "space-1",
                "nodeId": "folder-1",
            }
        },
    ) as m_post, patch.object(
        source,
        "_resolve_folder_parent_dentry_id",
        new_callable=AsyncMock,
        return_value="folder-dentry-1",
    ) as m_resolve_parent, patch.object(
        source,
        "_list_space_directory_items",
        side_effect=lambda **kwargs: _dirs(),
    ) as m_dirs:
        await source._probe_scope(entry=entry, access_token="token")

    m_post.assert_awaited_once()
    m_resolve_parent.assert_awaited_once_with(
        space_id="space-1",
        node_id="folder-1",
        access_token="token",
    )
    m_dirs.assert_called_once()


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
async def test_generate_entities_http_doc_prefers_block_tree_content_flow():
    """HTTP docs should prefer block-tree extraction over downloadInfo flow."""
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
        "_extract_doc_content",
        new_callable=AsyncMock,
        return_value=("我是猪", "success", True),
    ) as m_extract:
        entities = []
        async for entity in source.generate_entities():
            entities.append(entity)

    m_query.assert_awaited_once()
    m_extract.assert_awaited_once()
    assert len(entities) == 1
    assert entities[0].title == "python.adoc"
    assert entities[0].raw_content == "我是猪"
    assert entities[0].content_source == "block_tree"
    assert entities[0].content_status == "success"


@pytest.mark.asyncio
async def test_discover_docs_space_full_prefers_knowledge_base_directories():
    """Space discovery should prefer knowledge-base directory traversal in space_full mode."""
    config = DingtalkConfig(
        links="space:space-1",
        operator_union_id="operator-1",
        discovery_mode="space_full",
    )
    source = await _make_source(config)
    entries = [ResolvedDingTalkEntry("space", "space-1", "space:space-1")]

    async def _kb_docs():
        yield {"dentryUuid": "doc-from-kb", "name": "KB Doc"}

    with patch.object(
        source,
        "_walk_space_docs_via_directories",
        side_effect=lambda **kwargs: _kb_docs(),
    ) as m_kb, patch.object(
        source,
        "_list_space_items",
        new_callable=AsyncMock,
    ) as m_drive:
        docs = []
        async for doc in source._discover_docs(entries=entries, access_token="token"):
            docs.append(doc)

    m_kb.assert_called_once()
    m_drive.assert_not_called()
    assert len(docs) == 1
    assert docs[0]["dentryUuid"] == "doc-from-kb"


@pytest.mark.asyncio
async def test_discover_docs_space_full_falls_back_to_drive_when_kb_discovery_fails():
    """Space discovery should fallback to drive list when KB traversal errors."""
    config = DingtalkConfig(
        links="space:space-1",
        operator_union_id="operator-1",
        discovery_mode="space_full",
    )
    source = await _make_source(config)
    entries = [ResolvedDingTalkEntry("space", "space-1", "space:space-1")]

    async def _drive_docs():
        yield {"id": "doc-from-drive", "name": "Drive Doc", "type": "doc"}

    with patch.object(
        source,
        "_walk_space_docs_via_directories",
        new_callable=AsyncMock,
        side_effect=RuntimeError("kb-failed"),
    ) as m_kb, patch.object(
        source,
        "_list_space_items",
        side_effect=lambda **kwargs: _drive_docs(),
    ) as m_drive:
        docs = []
        async for doc in source._discover_docs(entries=entries, access_token="token"):
            docs.append(doc)

    m_kb.assert_awaited_once()
    m_drive.assert_called_once()
    assert len(docs) == 1
    assert docs[0]["id"] == "doc-from-drive"


@pytest.mark.asyncio
async def test_discover_docs_supports_mixed_doc_and_space_entries():
    """Discovery should handle doc entry and space entry together."""
    config = DingtalkConfig(
        links="doc:doc-direct,space:space-1",
        operator_union_id="operator-1",
        discovery_mode="space_full",
    )
    source = await _make_source(config)
    entries = [
        ResolvedDingTalkEntry("doc", "doc-direct", "doc:doc-direct"),
        ResolvedDingTalkEntry("space", "space-1", "space:space-1"),
    ]

    async def _kb_docs():
        yield {"dentryUuid": "doc-from-kb", "name": "KB Doc"}

    with patch.object(
        source,
        "_walk_space_docs_via_directories",
        side_effect=lambda **kwargs: _kb_docs(),
    ):
        docs = []
        async for doc in source._discover_docs(entries=entries, access_token="token"):
            docs.append(doc)

    discovered_ids = [source._extract_doc_id(item) for item in docs]
    assert "doc-direct" in discovered_ids
    assert "doc-from-kb" in discovered_ids


@pytest.mark.asyncio
async def test_discover_docs_http_folder_link_expands_children():
    """HTTP /nodes folder links should expand to children docs."""
    config = DingtalkConfig(
        links="https://alidocs.dingtalk.com/i/nodes/vNG4YZ7JnpM5MZkPuZ9zM0w9W2LD0oRE",
        operator_union_id="operator-1",
        discovery_mode="space_full",
    )
    source = await _make_source(config)
    entries = [
        ResolvedDingTalkEntry(
            "doc",
            "vNG4YZ7JnpM5MZkPuZ9zM0w9W2LD0oRE",
            "https://alidocs.dingtalk.com/i/nodes/vNG4YZ7JnpM5MZkPuZ9zM0w9W2LD0oRE",
        )
    ]

    async def _kb_docs():
        yield {"dentryUuid": "doc-1", "name": "Doc 1"}
        yield {"dentryUuid": "doc-2", "name": "Doc 2"}
        yield {"dentryUuid": "doc-3", "name": "Doc 3"}

    with patch.object(
        source,
        "_query_node_by_url",
        new_callable=AsyncMock,
        return_value={
            "type": "FOLDER",
            "hasChildren": True,
            "workspaceId": "space-1",
            "nodeId": "folder-1",
        },
    ) as m_query, patch.object(
        source,
        "_resolve_folder_parent_dentry_id",
        new_callable=AsyncMock,
        return_value="dentry-1",
    ) as m_resolve_parent, patch.object(
        source,
        "_walk_space_docs_via_directories",
        side_effect=lambda **kwargs: _kb_docs(),
    ) as m_walk:
        docs = []
        async for doc in source._discover_docs(entries=entries, access_token="token"):
            docs.append(doc)

    m_query.assert_awaited_once()
    m_resolve_parent.assert_awaited_once_with(
        space_id="space-1",
        node_id="folder-1",
        access_token="token",
    )
    m_walk.assert_called_once()
    assert m_walk.call_args.kwargs["parent_dentry_id"] == "dentry-1"
    assert len(docs) == 3
    assert {source._extract_doc_id(doc) for doc in docs} == {"doc-1", "doc-2", "doc-3"}

