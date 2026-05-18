"""Errors for YAML source import."""


class SourceImportError(ValueError):
    """Base error for import processing."""

    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.field = field
