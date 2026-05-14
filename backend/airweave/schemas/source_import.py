"""Schemas for YAML-based source import."""

from typing import Optional

from pydantic import BaseModel, Field


class SourceImportRequest(BaseModel):
    """Request body for importing source connections from YAML."""

    collection_id: str = Field(..., description="Readable collection ID to import into")
    yaml: str = Field(..., description="YAML content")
    dry_run: bool = Field(
        default=True,
        description="Validate only when true; create source connections when false",
    )


class SourceImportResultItem(BaseModel):
    """Per-entry import result."""

    index: int
    source_type: str
    name: str
    status: str
    source_connection_id: Optional[str] = None
    error_code: Optional[str] = None
    field: Optional[str] = None
    message: Optional[str] = None


class SourceImportSummary(BaseModel):
    """Aggregated import summary."""

    total: int = 0
    valid: int = 0
    created: int = 0
    failed: int = 0


class SourceImportResponse(BaseModel):
    """Response for YAML source import."""

    collection_id: str
    dry_run: bool
    summary: SourceImportSummary
    results: list[SourceImportResultItem]
