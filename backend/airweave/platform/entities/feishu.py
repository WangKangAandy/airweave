"""Feishu entity schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse RFC3339 datetime to naive UTC datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


class FeishuDocxEntity(BaseEntity):
    """Feishu docx document entity."""

    doc_token: str = AirweaveField(
        ...,
        description="Docx token in Feishu.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Document title.",
        embeddable=True,
        is_name=True,
    )
    raw_content: str = AirweaveField(
        default="",
        description="Raw text content returned by Feishu docx raw_content API.",
        embeddable=True,
    )
    folder_token: str = AirweaveField(
        default="",
        description="Parent folder token in Feishu Drive.",
        embeddable=False,
    )
    owner_id: Optional[str] = AirweaveField(
        default=None,
        description="Owner identifier (if available).",
        embeddable=False,
    )
    url: str = AirweaveField(
        default="",
        description="Web URL for this document.",
        embeddable=False,
        unhashable=True,
    )
    created_time: Optional[datetime] = AirweaveField(
        default=None,
        description="Creation timestamp.",
        is_created_at=True,
    )
    updated_time: Optional[datetime] = AirweaveField(
        default=None,
        description="Last edit timestamp.",
        is_updated_at=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for this document."""
        return self.url or f"https://feishu.cn/docx/{self.doc_token}"
