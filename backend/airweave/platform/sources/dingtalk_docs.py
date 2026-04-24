"""Dingtalk source implementation (MVP scaffold)."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import (
    SourceEntityForbiddenError,
    SourceEntityNotFoundError,
    SourceError,
)
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import DingtalkAuthConfig
from airweave.platform.configs.config import DingtalkConfig
from airweave.platform.decorators import source
from airweave.platform.entities.dingtalk_docs import DingtalkDocEntity
from airweave.platform.entities._base import BaseEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.resolvers.dingtalk import (
    DingTalkEntryResolver,
    ResolvedDingTalkEntry,
)
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

DINGTALK_API_BASE = "https://api.dingtalk.com"


@source(
    name="Dingtalk",
    short_name="dingtalk",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=DingtalkAuthConfig,
    config_class=DingtalkConfig,
    labels=["Knowledge Base", "Document Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.CONNECTION,
)
class DingtalkSource(BaseSource):
    """Dingtalk source with strict MVP constraints."""

    API_PATHS = {
        "token": "/v1.0/oauth2/accessToken",
        "space_files": "/v1.0/drive/spaces/{space_id}/files",
        "folder_files": "/v1.0/drive/folders/{folder_id}/files",
        "space_directories": "/v2.0/doc/spaces/{space_id}/directories",
        "doc_blocks": "/v1.0/docs/{doc_id}/blocks",
        "doc_content": "/v1.0/docs/{doc_id}/content",
        "doc_meta": "/v1.0/docs/{doc_id}",
        "wiki_query_by_url": "/v2.0/wiki/nodes/queryByUrl",
        "doc_query_dentry_id": "/v2.0/doc/dentries/{dentry_uuid}/queryDentryId",
        "storage_download_info": "/v1.0/storage/spaces/{space_id}/dentries/{dentry_id}/downloadInfos/query",
    }

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: DingtalkConfig,
    ) -> "DingtalkSource":
        """Create and configure a DingTalk source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.config = config
        instance.entry_resolver = DingTalkEntryResolver()
        return instance

    async def _get_access_token(self) -> str:
        """Return an access token for DingTalk OpenAPI.

        For direct auth, exchange app_key/app_secret per request.
        For non-credential providers, fallback to token provider token.
        """
        if self.auth.provider_kind != AuthProviderKind.CREDENTIAL:
            return await self.auth.get_token()

        credentials = self.auth.credentials
        payload = {
            "appKey": credentials.app_key,
            "appSecret": credentials.app_secret,
        }
        response = await self.http_client.post(
            f"{DINGTALK_API_BASE}{self.API_PATHS['token']}",
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
        access_token = data.get("accessToken")
        if not access_token:
            raise ValueError("DingTalk accessToken missing in auth response")
        return str(access_token)

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
        params: Optional[dict] = None,
    ) -> dict:
        """Issue authenticated GET request to DingTalk OpenAPI."""
        response = await self.http_client.get(
            f"{DINGTALK_API_BASE}{path}",
            headers={"x-acs-dingtalk-access-token": access_token},
            params=params or {},
            timeout=30.0,
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post(
        self,
        path: str,
        *,
        access_token: str,
        payload: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Issue authenticated POST request to DingTalk OpenAPI."""
        response = await self.http_client.post(
            f"{DINGTALK_API_BASE}{path}",
            headers={
                "x-acs-dingtalk-access-token": access_token,
                "Content-Type": "application/json",
            },
            params=params or {},
            json=payload or {},
            timeout=30.0,
        )
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _resolve_primary_entries(self) -> list[ResolvedDingTalkEntry]:
        """Resolve configured primary entries with links-first priority."""
        if self.config.links:
            resolved = await self.entry_resolver.resolve_many(self.config.links)
            entries = resolved.resolved_entries
            if resolved.invalid_entries:
                self.logger.warning(
                    "dingtalk: skipped invalid links: %s",
                    ", ".join(resolved.invalid_entries[:5]),
                )
            if entries:
                return entries
            raise ValueError("No valid DingTalk links after normalization")

        if self.config.root_space_id:
            return [
                ResolvedDingTalkEntry(
                    entry_type="space",
                    token=self.config.root_space_id,
                    source=f"space:{self.config.root_space_id}",
                )
            ]
        if self.config.root_folder_id:
            return [
                ResolvedDingTalkEntry(
                    entry_type="folder",
                    token=self.config.root_folder_id,
                    source=f"folder:{self.config.root_folder_id}",
                )
            ]

        raise ValueError("No primary entry configured: provide links or one root ID")

    def _operator_params(self) -> dict[str, str]:
        """Return optional operator scope params for API calls."""
        operator_union_id = (self.config.operator_union_id or "").strip()
        if not operator_union_id:
            return {}
        return {"operatorUnionId": operator_union_id}

    def _wiki_operator_params(self) -> dict[str, str]:
        """Return operator params required by wiki queryByUrl endpoints."""
        operator_union_id = (self.config.operator_union_id or "").strip()
        if not operator_union_id:
            return {}
        return {"operatorId": operator_union_id}

    def _is_http_entry_source(self, source: str) -> bool:
        """Return whether entry source is a raw http(s) URL from UI input."""
        lowered = (source or "").strip().lower()
        return lowered.startswith("http://") or lowered.startswith("https://")

    def _normalize_entry_url(self, source: str) -> str:
        """Strip querystring from source URL for stable queryByUrl matching."""
        return (source or "").split("?", 1)[0]

    async def _probe_doc_link_scope(self, *, entry: ResolvedDingTalkEntry, access_token: str) -> None:
        """Validate doc links via wiki queryByUrl instead of docs/{id}/blocks."""
        wiki_params = self._wiki_operator_params()
        if not wiki_params:
            raise ValueError(
                "operator_union_id is required for DingTalk doc links. "
                "Run OAuth probe to auto-fill this value."
            )
        data = await self._post(
            self.API_PATHS["wiki_query_by_url"],
            access_token=access_token,
            params=wiki_params,
            payload={"url": self._normalize_entry_url(entry.source)},
        )
        node = data.get("node") if isinstance(data, dict) else None
        if not isinstance(node, dict):
            return
        node_type = str(node.get("type") or "").upper()
        if node_type != "FOLDER" and not bool(node.get("hasChildren")):
            return
        space_id = str(node.get("workspaceId") or "")
        node_id = str(node.get("nodeId") or "")
        if not space_id or not node_id:
            return
        parent_dentry_id = await self._resolve_folder_parent_dentry_id(
            space_id=space_id,
            node_id=node_id,
            access_token=access_token,
        )
        # Folder link scope must also verify directory-list permission.
        async for _ in self._list_space_directory_items(
            space_id=space_id,
            access_token=access_token,
            parent_dentry_id=parent_dentry_id,
            page_size=1,
        ):
            break

    async def _query_node_by_url(
        self, *, source_url: str, access_token: str
    ) -> dict[str, Any] | None:
        """Resolve wiki node metadata by URL for alidocs-style entries."""
        wiki_params = self._wiki_operator_params()
        if not wiki_params:
            return None
        data = await self._post(
            self.API_PATHS["wiki_query_by_url"],
            access_token=access_token,
            params=wiki_params,
            payload={"url": self._normalize_entry_url(source_url)},
        )
        node = data.get("node") if isinstance(data, dict) else None
        return node if isinstance(node, dict) else None

    async def _resolve_dentry_id(
        self, *, dentry_uuid: str, access_token: str
    ) -> tuple[str, str] | None:
        """Resolve (space_id, dentry_id) from dentry UUID."""
        wiki_params = self._wiki_operator_params()
        if not wiki_params:
            return None
        data = await self._get(
            self.API_PATHS["doc_query_dentry_id"].format(dentry_uuid=dentry_uuid),
            access_token=access_token,
            params=wiki_params,
        )
        space_id = str(data.get("spaceId") or "")
        dentry_id = str(data.get("dentryId") or "")
        if not (space_id and dentry_id):
            return None
        return space_id, dentry_id

    async def _resolve_folder_parent_dentry_id(
        self,
        *,
        space_id: str,
        node_id: str,
        access_token: str,
    ) -> str:
        """Resolve folder parent dentry id used by directory listing.

        queryByUrl returns nodeId (uuid-like), while directory listing can require
        numeric/alternate dentryId in some workspaces. Prefer queryDentryId first,
        then fallback to nodeId when resolution is unavailable.
        """
        resolved = await self._resolve_dentry_id(dentry_uuid=node_id, access_token=access_token)
        if resolved:
            resolved_space_id, resolved_dentry_id = resolved
            if resolved_space_id == space_id and resolved_dentry_id:
                return resolved_dentry_id

        try:
            async for item in self._list_space_directory_items(
                space_id=space_id,
                access_token=access_token,
                parent_dentry_id=None,
                page_size=200,
            ):
                item_uuid = str(item.get("dentryUuid") or "")
                if item_uuid == node_id:
                    mapped = str(item.get("dentryId") or "")
                    if mapped:
                        return mapped
        except Exception:
            # Fallback to nodeId for compatibility with workspaces where it works.
            pass

        return node_id

    def _operator_union_id(self) -> str:
        """Return normalized operator union id."""
        return (self.config.operator_union_id or "").strip()

    def _extract_text_from_download_payload(self, payload: Any) -> str:
        """Extract best-effort text from downloaded JSON payload."""
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload
        if isinstance(payload, list):
            parts = [self._extract_text_from_download_payload(item) for item in payload]
            return "\n".join([p for p in parts if p.strip()])
        if isinstance(payload, dict):
            for key in ("text", "content", "plainText", "plain_text", "title", "name"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            parts = [self._extract_text_from_download_payload(v) for v in payload.values()]
            return "\n".join([p for p in parts if p.strip()])
        return str(payload)

    async def _download_dentry_text_content(
        self, *, space_id: str, dentry_id: str, access_token: str
    ) -> tuple[str, str]:
        """Download file content from storage downloadInfos API."""
        operator_union_id = self._operator_union_id()
        if not operator_union_id:
            return "", "unsupported"

        data = await self._post(
            self.API_PATHS["storage_download_info"].format(space_id=space_id, dentry_id=dentry_id),
            access_token=access_token,
            params={"unionId": operator_union_id},
            payload={"option": {"preferIntranet": False}},
        )
        signature_info = data.get("headerSignatureInfo") if isinstance(data, dict) else None
        if not isinstance(signature_info, dict):
            return "", "unsupported"

        resource_urls = signature_info.get("resourceUrls") or []
        resource_headers = signature_info.get("headers") or {}
        if not isinstance(resource_urls, list) or not resource_urls:
            return "", "empty"
        if not isinstance(resource_headers, dict):
            resource_headers = {}

        for resource_url in resource_urls:
            if not isinstance(resource_url, str) or not resource_url:
                continue
            response = await self.http_client.get(
                resource_url,
                headers=resource_headers,
                timeout=60.0,
            )
            if response.status_code < 200 or response.status_code >= 300:
                continue

            try:
                text = response.content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = response.content.decode("utf-8", errors="ignore")
                except Exception:
                    continue

            text = (text or "").strip()
            if not text:
                continue

            parsed_text = text
            if text.startswith("{") or text.startswith("["):
                try:
                    parsed = response.json()
                    parsed_text = self._extract_text_from_download_payload(parsed)
                except Exception:
                    parsed_text = text

            cleaned = self.clean_content_for_embedding(parsed_text)
            if cleaned.strip():
                return cleaned, "success"

        return "", "empty"

    async def _extract_http_doc_content(
        self, *, doc: dict[str, Any], access_token: str
    ) -> tuple[str, str]:
        """Extract content for alidocs http links via official dentry download flow."""
        node_id = str(doc.get("id") or "")
        if not node_id:
            return "", "unsupported"

        dentry_info = await self._resolve_dentry_id(dentry_uuid=node_id, access_token=access_token)
        if not dentry_info:
            return "", "unsupported"
        space_id, dentry_id = dentry_info
        doc["space_id"] = space_id
        doc["dentry_id"] = dentry_id

        return await self._download_dentry_text_content(
            space_id=space_id,
            dentry_id=dentry_id,
            access_token=access_token,
        )

    async def _probe_scope(
        self,
        *,
        entry: ResolvedDingTalkEntry,
        access_token: str,
    ) -> None:
        """Best-effort scope probe: list/read one unit based on entry type."""
        # API paths are kept explicit and isolated here for easy replacement once
        # official endpoint mapping is finalized in integration tests.
        if entry.entry_type == "space":
            await self._get(
                f"/v1.0/drive/spaces/{entry.token}/files",
                access_token=access_token,
                params={"size": 1, **self._operator_params()},
            )
            return
        if entry.entry_type == "folder":
            await self._get(
                f"/v1.0/drive/folders/{entry.token}/files",
                access_token=access_token,
                params={"size": 1, **self._operator_params()},
            )
            return
        if self._is_http_entry_source(entry.source):
            await self._probe_doc_link_scope(entry=entry, access_token=access_token)
            return
        await self._get(
            f"/v1.0/docs/{entry.token}/blocks",
            access_token=access_token,
            params={"size": 1, **self._operator_params()},
        )

    def _extract_items(self, data: dict) -> list[dict]:
        """Extract list-like payload from various DingTalk response shapes."""
        if not isinstance(data, dict):
            return []
        candidates = [
            data.get("items"),
            data.get("list"),
            data.get("files"),
            (data.get("data") or {}).get("items"),
            (data.get("data") or {}).get("list"),
            (data.get("data") or {}).get("files"),
            (data.get("result") or {}).get("items"),
            (data.get("result") or {}).get("list"),
            (data.get("result") or {}).get("files"),
        ]
        for candidate in candidates:
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        return []

    def _extract_doc_id(self, item: dict) -> str:
        """Extract a document identifier from a discovered item."""
        for key in (
            "doc_id",
            "docId",
            "docKey",
            "doc_key",
            "dentryId",
            "dentry_id",
            "dentry_uuid",
            "dentryUuid",
            "id",
            "token",
        ):
            value = item.get(key)
            if value:
                return str(value)
        return ""

    def _candidate_doc_ids(self, item: dict) -> list[str]:
        """Return ordered candidate identifiers for docs content APIs."""
        candidates: list[str] = []
        for key in (
            "doc_id",
            "docId",
            "docKey",
            "doc_key",
            "dentryId",
            "dentry_id",
            "dentry_uuid",
            "dentryUuid",
            "id",
            "token",
        ):
            value = item.get(key)
            if not value:
                continue
            text = str(value)
            if text not in candidates:
                candidates.append(text)
        return candidates

    def _extract_space_id(self, item: dict) -> str:
        """Extract a space/workspace identifier from item payload."""
        for key in ("space_id", "spaceId", "workspaceId", "workspace_id"):
            value = item.get(key)
            if value:
                return str(value)
        return ""

    def _extract_item_type(self, item: dict) -> str:
        """Extract normalized item type."""
        raw = (
            item.get("type")
            or item.get("dentryType")
            or item.get("contentType")
            or item.get("item_type")
            or item.get("resource_type")
            or item.get("kind")
            or ""
        )
        return str(raw).lower()

    def _is_doc_type(self, item: dict) -> bool:
        """Check whether an item should be treated as a document."""
        item_type = self._extract_item_type(item)
        if not item_type:
            return True
        return any(
            token in item_type
            for token in ("doc", "sheet", "wiki", "file", "alidoc", "document")
        )

    def _is_folder_type(self, item: dict) -> bool:
        """Check whether an item should be treated as folder-like."""
        item_type = self._extract_item_type(item)
        return any(token in item_type for token in ("folder", "space", "directory"))

    def _extract_directory_children(self, data: dict) -> list[dict]:
        """Extract children array from directory endpoint payload."""
        if not isinstance(data, dict):
            return []
        children = (
            data.get("children")
            or (data.get("data") or {}).get("children")
            or (data.get("result") or {}).get("children")
            or []
        )
        if not isinstance(children, list):
            return []
        return [item for item in children if isinstance(item, dict)]

    async def _list_space_directory_items(
        self,
        *,
        space_id: str,
        access_token: str,
        parent_dentry_id: str | None = None,
        page_size: int = 200,
    ) -> AsyncGenerator[dict, None]:
        """List directory children for a space using knowledge-base APIs."""
        next_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "maxResults": page_size,
                **self._wiki_operator_params(),
            }
            if parent_dentry_id:
                params["dentryId"] = parent_dentry_id
            if next_token:
                params["nextToken"] = next_token

            data = await self._get(
                self.API_PATHS["space_directories"].format(space_id=space_id),
                access_token=access_token,
                params=params,
            )
            children = self._extract_directory_children(data)
            for child in children:
                yield child

            has_more = (
                data.get("hasMore")
                if isinstance(data, dict)
                else False
            )
            next_token = (
                data.get("nextToken")
                or (data.get("data") or {}).get("nextToken")
                or (data.get("result") or {}).get("nextToken")
            )
            if not has_more or not next_token:
                break
            next_token = str(next_token)

    async def _walk_space_docs_via_directories(
        self,
        *,
        space_id: str,
        access_token: str,
        parent_dentry_id: str | None = None,
        depth: int = 0,
        seen_folders: set[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Recursively traverse knowledge-base directory tree for docs."""
        folders = seen_folders if seen_folders is not None else set()
        async for item in self._list_space_directory_items(
            space_id=space_id,
            access_token=access_token,
            parent_dentry_id=parent_dentry_id,
        ):
            if self._is_doc_type(item):
                yield item
                continue
            if not self._is_folder_type(item):
                continue
            if depth >= self.config.max_folder_depth:
                continue
            folder_id = self._extract_doc_id(item)
            if not folder_id or folder_id in folders:
                continue
            folders.add(folder_id)
            async for child in self._walk_space_docs_via_directories(
                space_id=space_id,
                access_token=access_token,
                parent_dentry_id=folder_id,
                depth=depth + 1,
                seen_folders=folders,
            ):
                yield child

    async def _list_space_items(
        self,
        *,
        space_id: str,
        access_token: str,
        page_size: int = 100,
    ) -> AsyncGenerator[dict, None]:
        """List items under a DingTalk space with pagination."""
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {
                "size": page_size,
                **self._operator_params(),
            }
            if cursor:
                params["cursor"] = cursor
            data = await self._get(
                self.API_PATHS["space_files"].format(space_id=space_id),
                access_token=access_token,
                params=params,
            )
            items = self._extract_items(data)
            for item in items:
                yield item
            next_cursor = (
                data.get("nextCursor")
                or (data.get("data") or {}).get("nextCursor")
                or (data.get("result") or {}).get("nextCursor")
            )
            has_more = bool(next_cursor)
            if not has_more:
                break
            cursor = str(next_cursor)

    async def _list_folder_items(
        self,
        *,
        folder_id: str,
        access_token: str,
        page_size: int = 100,
    ) -> AsyncGenerator[dict, None]:
        """List items under a DingTalk folder with pagination."""
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {
                "size": page_size,
                **self._operator_params(),
            }
            if cursor:
                params["cursor"] = cursor
            data = await self._get(
                self.API_PATHS["folder_files"].format(folder_id=folder_id),
                access_token=access_token,
                params=params,
            )
            items = self._extract_items(data)
            for item in items:
                yield item
            next_cursor = (
                data.get("nextCursor")
                or (data.get("data") or {}).get("nextCursor")
                or (data.get("result") or {}).get("nextCursor")
            )
            if not next_cursor:
                break
            cursor = str(next_cursor)

    async def _walk_folder_docs(
        self,
        *,
        folder_id: str,
        access_token: str,
        depth: int,
        seen_folders: set[str],
    ) -> AsyncGenerator[dict, None]:
        """Depth-limited DFS walk for folder-scoped discovery."""
        if folder_id in seen_folders:
            return
        seen_folders.add(folder_id)
        async for item in self._list_folder_items(folder_id=folder_id, access_token=access_token):
            if self._is_doc_type(item):
                yield item
                continue
            if self._is_folder_type(item) and depth < self.config.max_folder_depth:
                child_folder_id = self._extract_doc_id(item)
                if child_folder_id:
                    async for child in self._walk_folder_docs(
                        folder_id=child_folder_id,
                        access_token=access_token,
                        depth=depth + 1,
                        seen_folders=seen_folders,
                    ):
                        yield child

    async def _discover_docs(
        self,
        *,
        entries: list[ResolvedDingTalkEntry],
        access_token: str,
    ) -> AsyncGenerator[dict, None]:
        """Discover document candidates from configured entries."""
        seen_docs: set[str] = set()
        for entry in entries:
            if entry.entry_type == "doc":
                if self._is_http_entry_source(entry.source):
                    node = await self._query_node_by_url(
                        source_url=entry.source,
                        access_token=access_token,
                    )
                    if isinstance(node, dict):
                        node_id = str(node.get("nodeId") or entry.token)
                        node_type = str(node.get("type") or "").upper()
                        if node_type == "FOLDER" or bool(node.get("hasChildren")):
                            space_id = str(node.get("workspaceId") or "")
                            if space_id and node_id:
                                parent_dentry_id = await self._resolve_folder_parent_dentry_id(
                                    space_id=space_id,
                                    node_id=node_id,
                                    access_token=access_token,
                                )
                                async for item in self._walk_space_docs_via_directories(
                                    space_id=space_id,
                                    access_token=access_token,
                                    parent_dentry_id=parent_dentry_id,
                                    depth=0,
                                    seen_folders={parent_dentry_id},
                                ):
                                    doc_id = self._extract_doc_id(item)
                                    if doc_id and doc_id not in seen_docs:
                                        seen_docs.add(doc_id)
                                        yield item
                                continue
                        doc = {
                            "id": node_id,
                            "title": str(node.get("name") or ""),
                            "url": str(node.get("url") or ""),
                            "space_id": str(node.get("workspaceId") or self.config.root_space_id),
                            "parent_id": str(node.get("parentId") or self.config.root_folder_id),
                            "source": entry.source,
                        }
                        doc_id = self._extract_doc_id(doc)
                        if doc_id and doc_id not in seen_docs:
                            seen_docs.add(doc_id)
                            yield doc
                        continue
                doc = {
                    "id": entry.token,
                    "title": "",
                    "url": "",
                    "space_id": self.config.root_space_id,
                    "parent_id": self.config.root_folder_id,
                    "source": entry.source,
                }
                doc_id = self._extract_doc_id(doc)
                if doc_id and doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    yield doc
                continue
            if entry.entry_type == "space":
                used_kb_discovery = False
                if self.config.discovery_mode == "space_full":
                    try:
                        async for item in self._walk_space_docs_via_directories(
                            space_id=entry.token,
                            access_token=access_token,
                        ):
                            used_kb_discovery = True
                            doc_id = self._extract_doc_id(item)
                            if not doc_id or doc_id in seen_docs:
                                continue
                            seen_docs.add(doc_id)
                            yield item
                    except Exception as exc:
                        self.logger.warning(
                            "dingtalk: knowledge-base directory discovery failed, fallback to drive list: %s",
                            exc,
                        )
                if used_kb_discovery:
                    continue
                async for item in self._list_space_items(
                    space_id=entry.token,
                    access_token=access_token,
                ):
                    if not self._is_doc_type(item):
                        continue
                    doc_id = self._extract_doc_id(item)
                    if doc_id and doc_id not in seen_docs:
                        seen_docs.add(doc_id)
                        yield item
                continue
            if entry.entry_type == "folder":
                async for item in self._walk_folder_docs(
                    folder_id=entry.token,
                    access_token=access_token,
                    depth=0,
                    seen_folders=set(),
                ):
                    doc_id = self._extract_doc_id(item)
                    if doc_id and doc_id not in seen_docs:
                        seen_docs.add(doc_id)
                        yield item

    def _flatten_block_text(self, value: Any) -> str:
        """Recursively extract plain text from nested block payload."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = [self._flatten_block_text(v) for v in value]
            return " ".join([p for p in parts if p.strip()])
        if isinstance(value, dict):
            for key in ("text", "content", "plain_text", "title"):
                if key in value and isinstance(value[key], str) and value[key].strip():
                    return value[key]
            if "rich_text" in value:
                return self._flatten_block_text(value["rich_text"])
            parts = [self._flatten_block_text(v) for v in value.values()]
            return " ".join([p for p in parts if p.strip()])
        return str(value)

    async def _get_doc_blocks(
        self,
        *,
        doc_id: str,
        access_token: str,
    ) -> list[dict]:
        """Fetch all blocks for a document with pagination."""
        blocks: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {
                "size": 200,
                **self._operator_params(),
            }
            if cursor:
                params["cursor"] = cursor
            data = await self._get(
                self.API_PATHS["doc_blocks"].format(doc_id=doc_id),
                access_token=access_token,
                params=params,
            )
            page_blocks = self._extract_items(data)
            blocks.extend(page_blocks)
            next_cursor = (
                data.get("nextCursor")
                or (data.get("data") or {}).get("nextCursor")
                or (data.get("result") or {}).get("nextCursor")
            )
            if not next_cursor:
                break
            cursor = str(next_cursor)
        return blocks

    async def _extract_doc_content(
        self,
        *,
        doc_id: str,
        access_token: str,
    ) -> tuple[str, str, bool]:
        """Extract doc content and return (content, status, has_any_block)."""
        blocks = await self._get_doc_blocks(doc_id=doc_id, access_token=access_token)
        if not blocks:
            return "", "empty", False
        content_parts: list[str] = []
        for block in blocks:
            text = self._flatten_block_text(block)
            if text.strip():
                content_parts.append(text.strip())
        merged = self.clean_content_for_embedding("\n\n".join(content_parts))
        if merged.strip():
            return merged, "success", True
        return "", "partial", True

    async def _extract_doc_content_direct_api(
        self,
        *,
        doc_id: str,
        access_token: str,
    ) -> tuple[str, str]:
        """Extract doc content from direct content API (if supported)."""
        data = await self._get(
            self.API_PATHS["doc_content"].format(doc_id=doc_id),
            access_token=access_token,
            params=self._operator_params(),
        )
        # Supported shapes: {"content": "..."} or {"data":{"content":"..."}}
        content = ""
        if isinstance(data, dict):
            content = str(
                data.get("content")
                or (data.get("data") or {}).get("content")
                or (data.get("result") or {}).get("content")
                or ""
            )
        cleaned = self.clean_content_for_embedding(content)
        if cleaned.strip():
            return cleaned, "success"
        return "", "empty"

    async def _extract_doc_content_fallback(
        self,
        *,
        doc_id: str,
        access_token: str,
    ) -> tuple[str, str]:
        """Fallback extraction from document metadata fields only."""
        data = await self._get(
            self.API_PATHS["doc_meta"].format(doc_id=doc_id),
            access_token=access_token,
            params=self._operator_params(),
        )
        if not isinstance(data, dict):
            return "", "unsupported"
        body = data.get("data") or data.get("result") or data
        raw_candidate = ""
        if isinstance(body, dict):
            raw_candidate = str(
                body.get("content")
                or body.get("raw_content")
                or body.get("description")
                or body.get("summary")
                or ""
            )
        cleaned = self.clean_content_for_embedding(raw_candidate)
        if cleaned.strip():
            return cleaned, "partial"
        return "", "unsupported"

    async def validate(self) -> None:
        """Validate credentials and MVP-required operator context."""
        # Auth validate: ensure token can be acquired.
        access_token = await self._get_access_token()
        entries = await self._resolve_primary_entries()
        if not entries:
            raise ValueError("No valid DingTalk entries for scope validation")

        # Scope validate: probe the first configured entry.
        try:
            await self._probe_scope(entry=entries[0], access_token=access_token)
        except SourceEntityForbiddenError as exc:
            raise ValueError(
                "OPERATOR_NO_PERMISSION: operator can authenticate but lacks read/list scope"
            ) from exc
        except SourceEntityNotFoundError as exc:
            raise ValueError("AUTH_OK_BUT_EMPTY_SCOPE: configured entry not found or not visible") from exc
        except SourceError as exc:
            raise ValueError(
                "DINGTALK_SCOPE_PROBE_FAILED: unable to validate current link/id with selected API path. "
                f"Upstream detail: {exc}"
            ) from exc

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from DingTalk docs.

        Current scaffold emits doc placeholders from resolved doc entries.
        Discovery and block-tree extraction will progressively replace this path.
        """
        del cursor, files, node_selections
        access_token = await self._get_access_token()
        entries = await self._resolve_primary_entries()
        stats: dict[str, int] = {key: 0 for key in ("success", "partial", "empty", "unsupported", "failed")}
        async for doc in self._discover_docs(entries=entries, access_token=access_token):
            if self._is_http_entry_source(str(doc.get("source") or "")):
                try:
                    node = await self._query_node_by_url(
                        source_url=str(doc.get("source") or ""),
                        access_token=access_token,
                    )
                    if node:
                        doc["id"] = str(node.get("nodeId") or doc.get("id") or "")
                        doc["title"] = str(node.get("name") or doc.get("title") or "")
                        doc["url"] = str(node.get("url") or doc.get("url") or "")
                        doc["space_id"] = str(
                            node.get("workspaceId") or doc.get("space_id") or self.config.root_space_id
                        )
                except Exception as exc:
                    self.logger.debug("dingtalk: queryByUrl metadata enrich failed: %s", exc)

            doc_ids = self._candidate_doc_ids(doc)
            if not doc_ids:
                continue
            doc_id = doc_ids[0]
            title = str(doc.get("title") or doc.get("name") or doc_id)
            self.logger.debug("dingtalk: processing doc %s (%s)", doc_id, title)
            status = "failed"
            source = "block_tree"
            raw_content = ""
            try:
                has_any_block = False
                succeeded_doc_id: str | None = None
                for candidate_id in doc_ids:
                    try:
                        raw_content, status, has_any_block = await self._extract_doc_content(
                            doc_id=candidate_id,
                            access_token=access_token,
                        )
                        doc_id = candidate_id
                        succeeded_doc_id = candidate_id
                        break
                    except SourceEntityNotFoundError:
                        continue
                    except SourceError:
                        continue
                    except Exception:
                        continue
                if succeeded_doc_id is None:
                    status = "empty"
                    raw_content = ""
                source = "block_tree"
                self.logger.debug(
                    "dingtalk: block_tree result doc=%s status=%s content_len=%s",
                    doc_id,
                    status,
                    len(raw_content),
                )
                if status in ("empty", "partial") and not raw_content.strip():
                    try:
                        direct_content, direct_status = await self._extract_doc_content_direct_api(
                            doc_id=doc_id,
                            access_token=access_token,
                        )
                        if direct_content.strip() or direct_status == "success":
                            raw_content = direct_content
                            status = "success" if direct_content.strip() else direct_status
                            source = "direct_api"
                            self.logger.debug(
                                "dingtalk: direct_api used doc=%s status=%s content_len=%s",
                                doc_id,
                                status,
                                len(raw_content),
                            )
                    except Exception:
                        # Fall through to fallback extraction.
                        pass

                if status in ("empty", "partial") and not raw_content.strip():
                    fallback_content, fallback_status = await self._extract_doc_content_fallback(
                        doc_id=doc_id,
                        access_token=access_token,
                    )
                    raw_content = fallback_content
                    status = fallback_status if fallback_status else status
                    source = "fallback"
                    self.logger.debug(
                        "dingtalk: fallback used doc=%s status=%s content_len=%s",
                        doc_id,
                        status,
                        len(raw_content),
                    )

                if not has_any_block and status in ("empty", "partial") and not raw_content.strip():
                    status = "unsupported"
            except SourceEntityNotFoundError:
                status = "empty"
                source = "fallback"
            except SourceEntityForbiddenError:
                status = "failed"
                source = "fallback"
            except Exception as exc:
                self.logger.warning(
                    "dingtalk: content extraction failed for doc %s: %s",
                    doc_id,
                    exc,
                )
                status = "failed"
                source = "fallback"

            if status == "success" and not raw_content.strip():
                status = "partial"
            if status not in stats:
                status = "failed"
            stats[status] += 1
            self.logger.debug(
                "dingtalk: final decision doc=%s source=%s status=%s",
                doc_id,
                source,
                status,
            )

            entity_id = f"dingtalk:doc:{doc_id}"
            yield DingtalkDocEntity(
                entity_id=entity_id,
                breadcrumbs=[],
                name=title,
                entity_key=entity_id,
                title=title,
                raw_content=raw_content,
                content_source=source,
                content_status=status,
                space_id=str(doc.get("space_id") or self.config.root_space_id),
                parent_id=str(doc.get("parent_id") or self.config.root_folder_id),
                path=str(doc.get("path") or doc.get("source") or ""),
                url=str(doc.get("url") or ""),
                owner_id=(str(doc.get("owner_id")) if doc.get("owner_id") else None),
                permission_mode=self.config.permission_mode,
                operator_id=((self.config.operator_union_id or "").strip() or None),
            )
        self.logger.info(
            "dingtalk content_status distribution: success=%s partial=%s empty=%s unsupported=%s failed=%s",
            stats["success"],
            stats["partial"],
            stats["empty"],
            stats["unsupported"],
            stats["failed"],
        )
