"""Feishu entry resolver implementation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from airweave.platform.sources.resolvers.base import BatchEntryResolver

if TYPE_CHECKING:
    from airweave.platform.sources.feishu import FeishuSource


@dataclass(frozen=True)
class ResolvedFeishuEntry:
    """Normalized Feishu entry resolved from input text."""

    entry_type: str  # folder | docx
    token: str
    source: str
    modified_epoch: int = 0


class FeishuEntryResolver(BatchEntryResolver[ResolvedFeishuEntry]):
    """Feishu-specific resolver for folder/wiki/docx links and tokens."""

    def __init__(self, source: FeishuSource):
        self._source = source

    async def resolve_one(
        self,
        entry: str,
        *,
        access_token: str,
    ) -> ResolvedFeishuEntry | None:
        """Resolve one entry into folder/docx input. Wiki entries are converted via get_node."""
        lowered = entry.lower()

        if lowered.startswith("folder:"):
            token = entry.split(":", 1)[1].strip()
            return ResolvedFeishuEntry(entry_type="folder", token=token, source=entry)
        if lowered.startswith("docx:"):
            token = entry.split(":", 1)[1].strip()
            return ResolvedFeishuEntry(entry_type="docx", token=token, source=entry)
        if lowered.startswith("wiki:"):
            wiki_token = entry.split(":", 1)[1].strip()
            return await self._resolve_wiki_entry(
                wiki_token=wiki_token,
                source=entry,
                access_token=access_token,
            )

        folder_match = re.search(r"/drive/folder/([A-Za-z0-9_-]+)", entry)
        if folder_match:
            return ResolvedFeishuEntry(
                entry_type="folder",
                token=folder_match.group(1),
                source=entry,
            )

        wiki_match = re.search(r"/wiki/([A-Za-z0-9_-]+)", entry)
        if wiki_match:
            return await self._resolve_wiki_entry(
                wiki_token=wiki_match.group(1),
                source=entry,
                access_token=access_token,
            )

        docx_match = re.search(r"/docx/([A-Za-z0-9_-]+)", entry)
        if docx_match:
            return ResolvedFeishuEntry(entry_type="docx", token=docx_match.group(1), source=entry)

        # Plain token fallback for backward compatibility.
        if "/" not in entry and "?" not in entry:
            if lowered.startswith("wik"):
                return await self._resolve_wiki_entry(
                    wiki_token=entry,
                    source=entry,
                    access_token=access_token,
                )
            if lowered.startswith("dox"):
                return ResolvedFeishuEntry(entry_type="docx", token=entry, source=entry)
            return ResolvedFeishuEntry(entry_type="folder", token=entry, source=entry)

        return None

    async def _resolve_wiki_entry(
        self,
        *,
        wiki_token: str,
        source: str,
        access_token: str,
    ) -> ResolvedFeishuEntry | None:
        """Resolve wiki node token to concrete docx token via wiki get_node API."""
        data = await self._source._get(
            "/wiki/v2/spaces/get_node",
            access_token=access_token,
            params={"token": wiki_token},
        )
        node = (data.get("data") or {}).get("node") or {}
        obj_type = (node.get("obj_type") or "").lower()
        obj_token = node.get("obj_token") or ""
        modified_epoch = 0
        raw_epoch = node.get("obj_edit_time")
        if raw_epoch:
            try:
                modified_epoch = int(str(raw_epoch))
            except ValueError:
                modified_epoch = 0

        if obj_type != "docx" or not obj_token:
            self._source.logger.warning(
                "feishu: wiki node skipped (unsupported obj_type=%s, source=%s)",
                obj_type or "unknown",
                source,
            )
            return None

        return ResolvedFeishuEntry(
            entry_type="docx",
            token=obj_token,
            source=source,
            modified_epoch=modified_epoch,
        )
