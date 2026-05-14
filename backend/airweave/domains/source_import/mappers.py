"""Mapper utilities for YAML source import."""

from dataclasses import dataclass
from typing import Any

from airweave.schemas.source_connection import DirectAuthentication, SourceConnectionCreate

from .errors import SourceImportError


@dataclass(frozen=True)
class SourceFieldSpec:
    """Field specification for one source type."""

    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()

    @property
    def allowed_fields(self) -> set[str]:
        """All supported fields."""
        return set(self.required_fields) | set(self.optional_fields)


FIELD_SPECS: dict[str, SourceFieldSpec] = {
    "github": SourceFieldSpec(
        required_fields=("personal_access_token", "repo_name"),
        optional_fields=("branch", "sync_pull_requests"),
    ),
    "gitlab": SourceFieldSpec(
        required_fields=("personal_access_token", "repo_url"),
        optional_fields=("branch",),
    ),
    "local_git": SourceFieldSpec(
        required_fields=("repo_path",),
        optional_fields=("branch", "follow_symlinks"),
    ),
    "dingtalk": SourceFieldSpec(
        required_fields=("app_key", "app_secret", "links", "operator_union_id"),
    ),
    "confluence": SourceFieldSpec(
        required_fields=("personal_access_token", "site_url"),
    ),
}


def validate_fields(source_type: str, payload: dict[str, Any]) -> None:
    """Validate required/unsupported fields for a source type."""
    spec = FIELD_SPECS.get(source_type)
    if spec is None:
        raise SourceImportError(
            "UNSUPPORTED_SOURCE_TYPE",
            f"Unsupported source type '{source_type}'",
            field="type",
        )

    missing = [field for field in spec.required_fields if field not in payload]
    if missing:
        raise SourceImportError(
            "MISSING_REQUIRED_FIELD",
            f"Missing required fields: {', '.join(missing)}",
            field=missing[0],
        )

    unknown = sorted(set(payload.keys()) - spec.allowed_fields)
    if unknown:
        raise SourceImportError(
            "INVALID_FIELD",
            f"Unsupported fields for '{source_type}': {', '.join(unknown)}",
            field=unknown[0],
        )


def to_source_connection_create(
    *,
    source_type: str,
    name: str,
    payload: dict[str, Any],
    collection_id: str,
) -> SourceConnectionCreate:
    """Map YAML entry to SourceConnectionCreate."""
    if source_type == "github":
        auth = {"personal_access_token": payload["personal_access_token"]}
        config = {
            "repo_name": payload["repo_name"],
            "branch": payload.get("branch", ""),
            "sync_pull_requests": payload.get("sync_pull_requests", False),
        }
    elif source_type == "gitlab":
        auth = {"personal_access_token": payload["personal_access_token"]}
        config = {
            "repo_url": payload["repo_url"],
            "branch": payload.get("branch", ""),
        }
    elif source_type == "local_git":
        auth = {}
        config = {
            "repo_path": payload["repo_path"],
            "branch": payload.get("branch", "main"),
            "follow_symlinks": payload.get("follow_symlinks", False),
        }
    elif source_type == "dingtalk":
        auth = {
            "app_key": payload["app_key"],
            "app_secret": payload["app_secret"],
        }
        config = {
            "links": payload["links"],
            "operator_union_id": payload["operator_union_id"],
        }
    elif source_type == "confluence":
        auth = {"api_key": payload["personal_access_token"]}
        config = {"site_url": payload["site_url"]}
    else:
        raise SourceImportError(
            "UNSUPPORTED_SOURCE_TYPE",
            f"Unsupported source type '{source_type}'",
            field="type",
        )

    return SourceConnectionCreate(
        name=name,
        short_name=source_type,
        readable_collection_id=collection_id,
        config=config,
        authentication=DirectAuthentication(credentials=auth),
        sync_immediately=True,
    )
