"""Feishu source implementation.

MVP scope:
- Direct auth using app_id/app_secret (tenant_access_token/internal)
- Traverse folder tree from folder_token
- Sync docx files via docx raw_content API
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import FeishuAuthConfig
from airweave.platform.configs.config import FeishuConfig
from airweave.platform.cursors import FeishuCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.feishu import FeishuDocxEntity, _parse_dt
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.resolvers.feishu import FeishuEntryResolver
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


def _drive_modified_epoch(item: Dict[str, Any]) -> int:
    """Parse Feishu Drive modified_time (seconds since epoch as string) to int."""
    mt = item.get("modified_time")
    if not mt:
        return 0
    try:
        return int(str(mt).strip())
    except ValueError:
        return 0


@source(
    name="Feishu",
    short_name="feishu",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=FeishuAuthConfig,
    config_class=FeishuConfig,
    labels=["Knowledge Base", "Document Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.CONNECTION,
    cursor_class=FeishuCursor,
)
class FeishuSource(BaseSource):
    """Feishu connector for syncing docx content from Feishu Drive folders."""

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: FeishuConfig,
    ) -> FeishuSource:
        """Create and configure a Feishu source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.entry_input = config.folder_token
        instance.max_folder_depth = config.max_folder_depth
        instance.entry_resolver = FeishuEntryResolver(instance)
        return instance

    async def validate(self) -> None:
        """Validate credentials and folder access."""
        token = await self._get_access_token()
        resolved = await self.entry_resolver.resolve_many(self.entry_input, access_token=token)
        if resolved.invalid_entries:
            raise ValueError(f"Invalid Feishu entries: {', '.join(resolved.invalid_entries[:3])}")
        if not resolved.resolved_entries:
            raise ValueError("No valid Feishu entries provided")

        for entry in resolved.resolved_entries:
            if entry.entry_type == "folder":
                async for _ in self._list_files(
                    folder_token=entry.token,
                    access_token=token,
                    page_size=1,
                ):
                    break
            elif entry.entry_type == "docx":
                await self._get_doc_title(doc_token=entry.token, access_token=token)

    async def _get_access_token(self) -> str:
        """Return an access token for Feishu API requests."""
        if self.auth.provider_kind != AuthProviderKind.CREDENTIAL:
            return await self.auth.get_token()

        credentials = self.auth.credentials
        payload = {"app_id": credentials.app_id, "app_secret": credentials.app_secret}
        response = await self.http_client.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        data = response.json()
        token = data.get("tenant_access_token")
        if not token:
            raise ValueError("Feishu tenant_access_token missing in auth response")
        return token

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(
        self,
        path: str,
        *,
        access_token: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Issue authenticated GET request to Feishu OpenAPI."""
        response = await self.http_client.get(
            f"{FEISHU_API_BASE}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params or {},
            timeout=30.0,
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _list_files(
        self,
        *,
        folder_token: str,
        access_token: str,
        page_size: int = 200,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List files under a Feishu Drive folder with pagination."""
        page_token: Optional[str] = None
        while True:
            params: Dict[str, Any] = {"folder_token": folder_token, "page_size": page_size}
            if page_token:
                params["page_token"] = page_token

            data = await self._get("/drive/v1/files", access_token=access_token, params=params)
            for item in data.get("data", {}).get("files", []):
                yield item

            if not data.get("data", {}).get("has_more"):
                break
            page_token = data.get("data", {}).get("next_page_token")
            if not page_token:
                break

    async def _get_doc_title(self, *, doc_token: str, access_token: str) -> str:
        """Get Feishu doc title."""
        data = await self._get(f"/docx/v1/documents/{doc_token}", access_token=access_token)
        return (data.get("data", {}) or {}).get("document", {}).get("title", "") or "Untitled"

    async def _get_doc_content(self, *, doc_token: str, access_token: str) -> str:
        """Get Feishu doc raw content."""
        data = await self._get(
            f"/docx/v1/documents/{doc_token}/raw_content",
            access_token=access_token,
        )
        return (data.get("data", {}) or {}).get("content", "") or ""

    async def _walk_folder(
        self,
        *,
        folder_token: str,
        access_token: str,
        depth: int,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Depth-limited DFS walk over Feishu Drive folders."""
        async for item in self._list_files(folder_token=folder_token, access_token=access_token):
            item_type = item.get("type", "")
            if item_type == "docx":
                yield item
                continue
            if item_type == "folder" and depth < self.max_folder_depth:
                child_folder_token = item.get("token", "")
                if child_folder_token:
                    async for child in self._walk_folder(
                        folder_token=child_folder_token,
                        access_token=access_token,
                        depth=depth + 1,
                    ):
                        yield child

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Feishu docx entities from folder traversal."""
        del files, node_selections
        cursor_data = cursor.data if cursor else {}
        last_epoch = 0
        raw_epoch = cursor_data.get("last_max_modified_epoch")
        if raw_epoch:
            try:
                last_epoch = int(str(raw_epoch).strip())
            except ValueError:
                last_epoch = 0

        access_token = await self._get_access_token()
        resolved = await self.entry_resolver.resolve_many(self.entry_input, access_token=access_token)
        if resolved.invalid_entries:
            self.logger.warning(
                "feishu: skipped invalid entries: %s",
                ", ".join(resolved.invalid_entries),
            )
        global_max_epoch = last_epoch
        seen_doc_tokens: set[str] = set()

        async def emit_doc(doc: Dict[str, Any], *, fallback_epoch: int = 0) -> AsyncGenerator[BaseEntity, None]:
            nonlocal global_max_epoch
            doc_token = doc.get("token", "")
            if not doc_token or doc_token in seen_doc_tokens:
                return
            seen_doc_tokens.add(doc_token)

            doc_epoch = _drive_modified_epoch(doc) or fallback_epoch
            global_max_epoch = max(global_max_epoch, doc_epoch)

            # Incremental: skip unchanged documents (no title/raw_content calls).
            if last_epoch > 0 and doc_epoch > 0 and doc_epoch <= last_epoch:
                return

            title = await self._get_doc_title(doc_token=doc_token, access_token=access_token)
            content = await self._get_doc_content(doc_token=doc_token, access_token=access_token)
            if not content.strip():
                return

            yield FeishuDocxEntity(
                entity_id=doc_token,
                breadcrumbs=[],
                name=title,
                created_at=_parse_dt(doc.get("created_time")),
                updated_at=_parse_dt(doc.get("modified_time")),
                doc_token=doc_token,
                title=title,
                raw_content=content,
                folder_token=doc.get("parent_token", "") or "",
                owner_id=(doc.get("owner_id") or ""),
                url=doc.get("url", "") or f"https://feishu.cn/docx/{doc_token}",
                created_time=_parse_dt(doc.get("created_time")),
                updated_time=_parse_dt(doc.get("modified_time")),
            )

        for entry in resolved.resolved_entries:
            if entry.entry_type == "folder":
                async for doc in self._walk_folder(
                    folder_token=entry.token,
                    access_token=access_token,
                    depth=0,
                ):
                    async for entity in emit_doc(doc):
                        yield entity
            elif entry.entry_type == "docx":
                synthetic_doc = {
                    "token": entry.token,
                    "parent_token": "",
                    "owner_id": "",
                    "url": f"https://my.feishu.cn/docx/{entry.token}",
                    "created_time": "",
                    "modified_time": str(entry.modified_epoch) if entry.modified_epoch else "",
                }
                async for entity in emit_doc(synthetic_doc, fallback_epoch=entry.modified_epoch):
                    yield entity

        if cursor:
            cursor.update(last_max_modified_epoch=str(global_max_epoch))
