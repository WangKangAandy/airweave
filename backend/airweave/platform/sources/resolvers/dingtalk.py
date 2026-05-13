"""DingTalk entry resolver implementation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from airweave.platform.sources.resolvers.base import BatchEntryResolver


@dataclass(frozen=True)
class ResolvedDingTalkEntry:
    """Normalized DingTalk entry resolved from input text."""

    entry_type: str  # doc | folder | space
    token: str
    source: str


class DingTalkEntryResolver(BatchEntryResolver[ResolvedDingTalkEntry]):
    """DingTalk-specific resolver for links and plain tokens."""

    async def resolve_one(
        self,
        entry: str,
        **kwargs,  # noqa: ARG002
    ) -> ResolvedDingTalkEntry | None:
        """Resolve one entry into a normalized DingTalk entry."""
        lowered = entry.lower()
        if lowered.startswith("doc:"):
            token = entry.split(":", 1)[1].strip()
            return ResolvedDingTalkEntry(entry_type="doc", token=token, source=entry) if token else None
        if lowered.startswith("folder:"):
            token = entry.split(":", 1)[1].strip()
            return (
                ResolvedDingTalkEntry(entry_type="folder", token=token, source=entry)
                if token
                else None
            )
        if lowered.startswith("space:"):
            token = entry.split(":", 1)[1].strip()
            return (
                ResolvedDingTalkEntry(entry_type="space", token=token, source=entry) if token else None
            )

        # URL-style parsing (best-effort patterns for DingTalk docs/knowledge-base links)
        node_match = re.search(r"/nodes/([A-Za-z0-9_-]+)", entry)
        if node_match:
            return ResolvedDingTalkEntry(entry_type="doc", token=node_match.group(1), source=entry)
        doc_match = re.search(r"(?:doc|docs)/([A-Za-z0-9_-]+)", entry)
        if doc_match:
            return ResolvedDingTalkEntry(entry_type="doc", token=doc_match.group(1), source=entry)
        space_path_match = re.search(r"/(?:space|spaces|workspace|workspaces)/([A-Za-z0-9_-]+)", entry)
        if space_path_match:
            return ResolvedDingTalkEntry(
                entry_type="space",
                token=space_path_match.group(1),
                source=entry,
            )
        space_query_match = re.search(r"(?:[?&](?:spaceId|workspaceId)=)([A-Za-z0-9_-]+)", entry)
        if space_query_match:
            return ResolvedDingTalkEntry(
                entry_type="space",
                token=space_query_match.group(1),
                source=entry,
            )
        folder_match = re.search(r"folder(?:/|=)([A-Za-z0-9_-]+)", entry)
        if folder_match:
            return ResolvedDingTalkEntry(
                entry_type="folder",
                token=folder_match.group(1),
                source=entry,
            )
        space_match = re.search(r"space(?:/|=)([A-Za-z0-9_-]+)", entry)
        if space_match:
            return ResolvedDingTalkEntry(
                entry_type="space",
                token=space_match.group(1),
                source=entry,
            )

        # Plain token fallback defaults to document token.
        if "/" not in entry and "?" not in entry and entry.strip():
            return ResolvedDingTalkEntry(entry_type="doc", token=entry.strip(), source=entry)

        return None
