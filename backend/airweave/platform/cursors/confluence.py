"""Confluence cursor schema for incremental sync."""

from pydantic import Field

from ._base import BaseCursor


class ConfluenceCursor(BaseCursor):
    """Confluence incremental sync cursor using last synced timestamp."""

    last_synced_at: str = Field(
        default="",
        description="ISO-8601 UTC timestamp of the latest processed Confluence page update",
    )
