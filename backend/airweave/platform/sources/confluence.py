"""Confluence source implementation for site URL + PAT mode.

This connector targets Confluence Server/Data Center style REST endpoints:
  - Discovery: /rest/api/space, /rest/api/content/search or /rest/api/content
  - Page details: /rest/api/content/{id}?expand=body.storage,version,space

It intentionally does NOT use Atlassian Cloud OAuth gateway flows
(`accessible-resources`, `cloud_id`, `/wiki/api/v2`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import quote

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError, SourceEntityNotFoundError
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import ConfluenceAuthConfig
from airweave.platform.configs.config import ConfluenceConfig
from airweave.platform.cursors import ConfluenceCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.confluence import (
    ConfluencePageDeletionEntity,
    ConfluencePageEntity,
    ConfluenceSpaceEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

DEFAULT_PAGE_LIMIT = 50


@source(
    name="Confluence",
    short_name="confluence",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=ConfluenceAuthConfig,
    config_class=ConfluenceConfig,
    labels=["Knowledge Base", "Documentation"],
    supports_continuous=True,
    rate_limit_level=RateLimitLevel.ORG,
    cursor_class=ConfluenceCursor,
)
class ConfluenceSource(BaseSource):
    """Confluence source connector using site URL + PAT authentication."""

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: ConfluenceConfig,
    ) -> ConfluenceSource:
        """Create a new Confluence source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_token = auth.credentials.api_key
        else:
            instance._api_token = await auth.get_token()
        instance._site_url = config.site_url.rstrip("/")
        instance._base_url = f"{instance._site_url}/rest/api"
        return instance

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        """Build Authorization + Accept headers."""
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",
        }

    @staticmethod
    def _parse_when(value: Optional[str]) -> Optional[datetime]:
        """Parse Confluence timestamp into UTC datetime."""
        if not value:
            return None
        raw = value.strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _to_cql_datetime(dt: datetime) -> str:
        """Format UTC datetime for Confluence CQL lastmodified filter."""
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")

    def _build_page_discovery_cql(self, *, space_key: str, since: Optional[datetime]) -> str:
        """Build CQL query for page discovery."""
        escaped_key = space_key.replace('"', '\\"')
        clauses = [f'type=page', f'space="{escaped_key}"']
        if since is not None:
            clauses.append(f'lastmodified >= "{self._to_cql_datetime(since)}"')
        return " and ".join(clauses)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an authenticated GET request to Confluence REST API."""
        url = path if path.startswith("http://") or path.startswith("https://") else f"{self._base_url}{path}"
        response = await self.http_client.get(url, headers=self._headers(), params=params)
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def _list_spaces(self) -> AsyncGenerator[dict[str, Any], None]:
        """Iterate spaces with pagination."""
        start = 0
        while True:
            data = await self._get("/space", params={"limit": DEFAULT_PAGE_LIMIT, "start": start})
            results = data.get("results") or []
            for space in results:
                if isinstance(space, dict):
                    yield space

            size = data.get("size", len(results))
            limit = data.get("limit", DEFAULT_PAGE_LIMIT)
            if not results or size < limit:
                break
            start += limit

    async def _discover_pages_for_space(self, space_key: str) -> AsyncGenerator[dict[str, Any], None]:
        """Discover pages for a space.

        Prefer content/search (CQL) and fall back to content list endpoint.
        """
        async for page in self._discover_pages_for_space_since(space_key=space_key, since=None):
            yield page

    async def _discover_pages_for_space_since(
        self,
        *,
        space_key: str,
        since: Optional[datetime],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Discover pages for a space with optional incremental lower-bound."""
        start = 0
        while True:
            cql = self._build_page_discovery_cql(space_key=space_key, since=since)
            data: Dict[str, Any]
            try:
                data = await self._get(
                    "/content/search",
                    params={
                        "cql": cql,
                        "limit": DEFAULT_PAGE_LIMIT,
                        "start": start,
                    },
                )
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(
                    "confluence: content/search unavailable for space=%s, fallback to /content: %s",
                    space_key,
                    e,
                )
                data = await self._get(
                    "/content",
                    params={
                        "spaceKey": space_key,
                        "type": "page",
                        "status": "current",
                        "limit": DEFAULT_PAGE_LIMIT,
                        "start": start,
                    },
                )

            results = data.get("results") or []
            for page in results:
                if isinstance(page, dict):
                    yield page

            size = data.get("size", len(results))
            limit = data.get("limit", DEFAULT_PAGE_LIMIT)
            if not results or size < limit:
                break
            start += limit

    async def _discover_trashed_pages_for_space(
        self,
        *,
        space_key: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Discover trashed pages for deletion compensation."""
        start = 0
        while True:
            data = await self._get(
                "/content",
                params={
                    "spaceKey": space_key,
                    "type": "page",
                    "status": "trashed",
                    "limit": DEFAULT_PAGE_LIMIT,
                    "start": start,
                },
            )
            results = data.get("results") or []
            for page in results:
                if isinstance(page, dict):
                    yield page

            size = data.get("size", len(results))
            limit = data.get("limit", DEFAULT_PAGE_LIMIT)
            if not results or size < limit:
                break
            start += limit

    async def _fetch_page_detail(self, page_id: str) -> Dict[str, Any]:
        """Fetch page details including storage body."""
        return await self._get(
            f"/content/{quote(page_id)}",
            params={"expand": "body.storage,version,space"},
        )

    async def _generate_page_entities(
        self,
        *,
        space_entity: ConfluenceSpaceEntity,
        files: FileService | None,
        since: Optional[datetime],
    ) -> AsyncGenerator[ConfluencePageEntity, None]:
        """Generate ConfluencePageEntity objects for one space."""
        breadcrumb = Breadcrumb(
            entity_id=space_entity.entity_id,
            name=space_entity.space_name or space_entity.space_key,
            entity_type=ConfluenceSpaceEntity.__name__,
        )

        async for page in self._discover_pages_for_space_since(
            space_key=space_entity.space_key,
            since=since,
        ):
            page_id = str(page.get("id") or "")
            if not page_id:
                continue

            try:
                page_details = await self._fetch_page_detail(page_id)
            except SourceEntityNotFoundError as e:
                # Page was deleted or no longer accessible between listing and detail fetch.
                # Log and continue without failing the entire sync.
                self.logger.warning(
                    "confluence: page detail 404 for space=%s id=%s: %s",
                    space_entity.space_key,
                    page_id,
                    e,
                )
                continue

            page_entity = ConfluencePageEntity.from_api(
                page_details,
                breadcrumbs=[breadcrumb],
                space_key=space_entity.space_key,
                site_url=self._site_url,
                base_url=self._site_url,
            )

            body_content = page_entity.body or ""
            html_content = (
                f"<!DOCTYPE html>\n<html>\n<head>\n"
                f"    <title>{page_entity.title or ''}</title>\n"
                f'    <meta charset="UTF-8">\n</head>\n<body>\n'
                f"{body_content}\n</body>\n</html>"
            )

            if files:
                try:
                    await files.save_bytes(
                        entity=page_entity,
                        content=html_content.encode("utf-8"),
                        filename_with_extension=f"{page_entity.name}.html",
                        logger=self.logger,
                    )
                    if not page_entity.local_path:
                        raise ValueError(f"Save failed - no local path set for {page_entity.name}")
                except FileSkippedException as e:
                    self.logger.debug(f"Skipping file: {e.reason}")
                    continue
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Failed to save page {page_entity.name}: {e}")
                    continue

            yield page_entity

    async def _generate_page_deletion_entities(
        self,
        *,
        space_entity: ConfluenceSpaceEntity,
    ) -> AsyncGenerator[ConfluencePageDeletionEntity, None]:
        """Generate deletion entities from trashed pages."""
        async for page in self._discover_trashed_pages_for_space(space_key=space_entity.space_key):
            page_id = str(page.get("id") or "").strip()
            if not page_id:
                continue
            yield ConfluencePageDeletionEntity(
                entity_id=page_id,
                breadcrumbs=[],
                name=f"Deleted {page.get('title') or page_id}",
                deletion_status="removed",
                page_key=page_id,
                title=str(page.get("title") or f"Deleted page {page_id}"),
                content_id=page_id,
                space_key=space_entity.space_key,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def validate(self) -> None:
        """Verify site URL + PAT by calling /user/current."""
        data = await self._get("/user/current")
        user_type = str(data.get("type") or "").lower()
        if user_type == "anonymous":
            raise SourceAuthError(
                "Confluence validation failed: authenticated request resolved to anonymous user"
            )

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Confluence space and page entities."""
        del node_selections

        self.logger.debug("Starting Confluence site-url entity generation process")

        since: Optional[datetime] = None
        if cursor and cursor.data:
            since = self._parse_when(cursor.data.get("last_synced_at"))

        latest_seen = since

        async for space in self._list_spaces():
            space_entity = ConfluenceSpaceEntity.from_api(space, site_url=self._site_url)
            yield space_entity

            async for page_entity in self._generate_page_entities(
                space_entity=space_entity,
                files=files,
                since=since,
            ):
                candidate_dt = page_entity.updated_at or page_entity.created_at
                if candidate_dt and (latest_seen is None or candidate_dt > latest_seen):
                    latest_seen = candidate_dt
                yield page_entity

            # Trashed listing is used as deletion compensation. Kept separate from CQL
            # because many Server/DC versions do not support `status=trashed` in CQL.
            async for deletion_entity in self._generate_page_deletion_entities(space_entity=space_entity):
                yield deletion_entity

        if cursor and latest_seen is not None:
            cursor.update(last_synced_at=latest_seen.astimezone(timezone.utc).isoformat())
