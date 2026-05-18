"""Source import domain module (YAML bulk import).

Import ``SourceImportService`` from ``airweave.domains.source_import.service`` when needed
to avoid pulling async/SQLAlchemy dependencies for lightweight imports (e.g. mappers only).
"""
