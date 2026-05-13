"""Shared resolver abstractions for multi-entry source inputs."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class BatchResolveResult[T]:
    """Batch resolution result for user-provided entries."""

    resolved_entries: list[T]
    invalid_entries: list[str]


class BatchEntryResolver[T](ABC):
    """Abstract base resolver for parsing and normalizing batch entry input."""

    def split_entries(self, raw: str) -> list[str]:
        """Split user input by spaces/commas/semicolons/new lines."""
        return [part.strip() for part in re.split(r"[\s,;，；]+", raw or "") if part.strip()]

    async def resolve_many(self, raw: str, **kwargs) -> BatchResolveResult[T]:
        """Resolve all entries and collect invalid ones instead of failing fast."""
        resolved_entries: list[T] = []
        invalid_entries: list[str] = []
        for entry in self.split_entries(raw):
            resolved = await self.resolve_one(entry, **kwargs)
            if resolved is None:
                invalid_entries.append(entry)
            else:
                resolved_entries.append(resolved)
        return BatchResolveResult(resolved_entries=resolved_entries, invalid_entries=invalid_entries)

    @abstractmethod
    async def resolve_one(self, entry: str, **kwargs) -> T | None:
        """Resolve a single entry to a normalized representation."""
