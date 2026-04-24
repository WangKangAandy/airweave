"""Dingtalk entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class DingtalkDocEntity(BaseEntity):
    """Dingtalk cloud document entity."""

    entity_key: str = AirweaveField(
        ...,
        description="Stable external ID in format dingtalk:{resource_type}:{resource_id}.",
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
        description="Aggregated markdown content extracted from DingTalk doc body.",
        embeddable=True,
    )
    content_source: Literal["block_tree", "direct_api", "fallback"] = AirweaveField(
        default="block_tree",
        description="Primary extraction path used for body content.",
        embeddable=False,
    )
    content_status: Literal["success", "partial", "empty", "unsupported", "failed"] = AirweaveField(
        default="failed",
        description="Extraction outcome for document body content.",
        embeddable=False,
    )
    space_id: str = AirweaveField(
        default="",
        description="DingTalk space identifier.",
        embeddable=False,
    )
    parent_id: str = AirweaveField(
        default="",
        description="Parent folder/document identifier.",
        embeddable=False,
    )
    path: str = AirweaveField(
        default="",
        description="Logical path under configured sync root.",
        embeddable=False,
    )
    url: str = AirweaveField(
        default="",
        description="Web URL for this document.",
        embeddable=False,
        unhashable=True,
    )
    owner_id: Optional[str] = AirweaveField(
        default=None,
        description="Owner identifier (if available from metadata).",
        embeddable=False,
    )
    permission_mode: str = AirweaveField(
        default="app_operator_scope",
        description="Indexing boundary marker for this entity.",
        embeddable=False,
    )
    operator_id: str = AirweaveField(
        default="",
        description="Operator union ID used as sync context.",
        embeddable=False,
    )
    created_time: Optional[datetime] = AirweaveField(
        default=None,
        description="Creation timestamp (if available).",
        is_created_at=True,
    )
    updated_time: Optional[datetime] = AirweaveField(
        default=None,
        description="Last modification timestamp (if available).",
        is_updated_at=True,
    )
