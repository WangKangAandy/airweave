from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from airweave.platform.entities.confluence import ConfluencePageEntity, ConfluenceSpaceEntity
from airweave.platform.sources.confluence import ConfluenceSource


def _make_source() -> ConfluenceSource:
    source = ConfluenceSource(auth=MagicMock(), logger=MagicMock(), http_client=MagicMock())
    source._site_url = "https://confluence.example.com"
    source._base_url = "https://confluence.example.com/rest/api"
    source._api_token = "token"
    return source


def test_build_page_discovery_cql_full_sync():
    source = _make_source()
    cql = source._build_page_discovery_cql(space_key="ENG", since=None)
    assert cql == 'type=page and space="ENG"'


def test_build_page_discovery_cql_incremental():
    source = _make_source()
    since = datetime(2026, 4, 25, 9, 40, tzinfo=timezone.utc)
    cql = source._build_page_discovery_cql(space_key="~kang.wang", since=since)
    assert cql == 'type=page and space="~kang.wang" and lastmodified >= "2026-04-25 09:40"'


@pytest.mark.asyncio
async def test_generate_entities_updates_cursor_with_latest_seen():
    source = _make_source()

    now = datetime.now(timezone.utc)
    older = now - timedelta(minutes=30)
    newer = now - timedelta(minutes=5)

    async def _spaces():
        yield {"id": "ENG", "name": "Engineering", "key": "ENG", "type": "global"}

    async def _pages(*, space_entity, files, since):  # noqa: ARG001
        yield ConfluencePageEntity(
            entity_id="1",
            breadcrumbs=[],
            name="p1",
            url="https://confluence.example.com/rest/api/content/1",
            size=0,
            file_type="html",
            mime_type="text/html",
            local_path=None,
            content_id="1",
            title="P1",
            space_id="ENG",
            space_key="ENG",
            body="<p>a</p>",
            version=1,
            status="current",
            site_url="https://confluence.example.com",
            created_at=older,
            updated_at=older,
        )
        yield ConfluencePageEntity(
            entity_id="2",
            breadcrumbs=[],
            name="p2",
            url="https://confluence.example.com/rest/api/content/2",
            size=0,
            file_type="html",
            mime_type="text/html",
            local_path=None,
            content_id="2",
            title="P2",
            space_id="ENG",
            space_key="ENG",
            body="<p>b</p>",
            version=1,
            status="current",
            site_url="https://confluence.example.com",
            created_at=newer,
            updated_at=newer,
        )

    async def _deletions(*, space_entity):  # noqa: ARG001
        if False:
            yield  # pragma: no cover

    source._list_spaces = _spaces
    source._generate_page_entities = _pages
    source._generate_page_deletion_entities = _deletions

    class _Cursor:
        def __init__(self):
            self.data = {}
            self.updated = {}

        def update(self, **fields):
            self.updated.update(fields)

    cursor = _Cursor()
    entities = []
    async for e in source.generate_entities(cursor=cursor, files=None, node_selections=None):
        entities.append(e)

    assert len(entities) == 3  # 1 space + 2 pages
    assert "last_synced_at" in cursor.updated
