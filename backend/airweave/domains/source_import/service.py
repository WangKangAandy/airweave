"""YAML source import service (application-layer orchestration)."""

from dataclasses import dataclass
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.domains.source_connections.protocols import SourceConnectionServiceProtocol
from airweave.domains.sources.protocols import SourceServiceProtocol
from airweave.schemas.source_import import (
    SourceImportResponse,
    SourceImportResultItem,
    SourceImportSummary,
)

from .errors import SourceImportError
from .mappers import to_source_connection_create, validate_fields


@dataclass(frozen=True)
class ImportEntry:
    """Flat import entry after parsing grouped YAML."""

    index: int
    source_type: str
    name: str
    payload: dict[str, Any]


class SourceImportService:
    """Handle YAML parsing, validation, and optional source creation."""

    SUPPORTED_TYPES = {"github", "gitlab", "local_git", "dingtalk", "confluence"}

    def __init__(
        self,
        *,
        source_connection_service: SourceConnectionServiceProtocol,
        source_service: SourceServiceProtocol,
    ) -> None:
        self._source_connection_service = source_connection_service
        self._source_service = source_service

    async def import_yaml(
        self,
        db: AsyncSession,
        *,
        collection_id: str,
        yaml_text: str,
        dry_run: bool,
        ctx: ApiContext,
    ) -> SourceImportResponse:
        """Validate or import source connections from YAML."""
        entries = self._parse_yaml(yaml_text)
        collection = await crud.collection.get_by_readable_id(db, collection_id, ctx)
        collection_display_name = collection.name
        results: list[SourceImportResultItem] = []
        valid_count = 0
        created_count = 0
        failed_count = 0

        for entry in entries:
            try:
                await self._ensure_supported_source(entry.source_type, ctx)
                source_schema = await self._source_service.get(entry.source_type, ctx)
                validate_fields(entry.source_type, entry.payload)
                create_obj = to_source_connection_create(
                    source_type=entry.source_type,
                    name=entry.name,
                    payload=entry.payload,
                    collection_id=collection_id,
                    source_display_name=source_schema.name,
                    collection_display_name=collection_display_name,
                )
                valid_count += 1

                if dry_run:
                    results.append(
                        SourceImportResultItem(
                            index=entry.index,
                            source_type=entry.source_type,
                            name=entry.name,
                            status="validated",
                        )
                    )
                    continue

                created = await self._source_connection_service.create(
                    db,
                    obj_in=create_obj,
                    ctx=ctx,
                )
                created_count += 1
                results.append(
                    SourceImportResultItem(
                        index=entry.index,
                        source_type=entry.source_type,
                        name=entry.name,
                        status="created",
                        source_connection_id=str(created.id),
                    )
                )
            except SourceImportError as exc:
                failed_count += 1
                results.append(
                    SourceImportResultItem(
                        index=entry.index,
                        source_type=entry.source_type,
                        name=entry.name,
                        status="failed",
                        error_code=exc.code,
                        field=exc.field,
                        message=str(exc),
                    )
                )
            except Exception as exc:
                failed_count += 1
                results.append(
                    SourceImportResultItem(
                        index=entry.index,
                        source_type=entry.source_type,
                        name=entry.name,
                        status="failed",
                        error_code="CREATE_FAILED",
                        message=str(exc),
                    )
                )

        return SourceImportResponse(
            collection_id=collection_id,
            dry_run=dry_run,
            summary=SourceImportSummary(
                total=len(entries),
                valid=valid_count,
                created=created_count,
                failed=failed_count,
            ),
            results=results,
        )

    async def _ensure_supported_source(self, source_type: str, ctx: ApiContext) -> None:
        """Ensure source exists in registry and is allowed for YAML import."""
        if source_type not in self.SUPPORTED_TYPES:
            raise SourceImportError(
                "UNSUPPORTED_SOURCE_TYPE",
                f"Unsupported source type '{source_type}'",
                field="type",
            )
        await self._source_service.get(source_type, ctx)

    def _parse_yaml(self, yaml_text: str) -> list[ImportEntry]:
        """Parse grouped YAML and flatten to typed entries."""
        try:
            payload = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise SourceImportError("INVALID_YAML", f"Invalid YAML: {exc}") from exc

        if not isinstance(payload, dict):
            raise SourceImportError("INVALID_SCHEMA", "YAML root must be an object")

        version = payload.get("version")
        if version != 1:
            raise SourceImportError("INVALID_VERSION", "version must be 1", field="version")

        raw_sources = payload.get("sources")
        if not isinstance(raw_sources, dict):
            raise SourceImportError("INVALID_SCHEMA", "sources must be an object", field="sources")

        entries: list[ImportEntry] = []
        idx = 0
        for source_type, named_configs in raw_sources.items():
            if not isinstance(named_configs, dict):
                raise SourceImportError(
                    "INVALID_SCHEMA",
                    f"sources.{source_type} must be an object of name->config",
                    field=f"sources.{source_type}",
                )
            for name, config in named_configs.items():
                if not isinstance(name, str) or not name.strip():
                    raise SourceImportError(
                        "INVALID_SCHEMA",
                        f"Invalid source name under type '{source_type}'",
                        field=f"sources.{source_type}",
                    )
                if not isinstance(config, dict):
                    raise SourceImportError(
                        "INVALID_SCHEMA",
                        f"Config for '{name}' under '{source_type}' must be an object",
                        field=f"sources.{source_type}.{name}",
                    )
                entries.append(
                    ImportEntry(
                        index=idx,
                        source_type=str(source_type),
                        name=name.strip(),
                        payload=config,
                    )
                )
                idx += 1

        return entries
