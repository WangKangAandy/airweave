"""Local Git repository source implementation for syncing local code repositories.

This source allows users to sync code from locally cloned Git repositories,
bypassing the need for GitHub API access and authentication. It reads files
directly from the local filesystem and uses GitPython to extract metadata.
"""

from __future__ import annotations

import asyncio
import mimetypes
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.platform.configs.auth import LocalGitAuthConfig
from airweave.platform.configs.config import LocalGitConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.github import (
    GitHubCodeFileEntity,
    GitHubDirectoryEntity,
    GitHubRepositoryEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.utils.file_extensions import (
    get_language_for_extension,
    is_text_file,
)
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Local Git",
    short_name="local_git",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class=LocalGitAuthConfig,
    config_class=LocalGitConfig,
    labels=["Code", "Local"],
    supports_continuous=False,
    supports_temporal_relevance=False,
)
class LocalGitSource(BaseSource):
    """Local Git repository source connector.

    Syncs code from locally cloned Git repositories by reading files directly
    from the filesystem. Uses GitPython to extract Git metadata and track changes.

    Key features:
    - No API authentication required
    - Works offline (no network dependency)
    - Supports file filtering by extension
    - Extracts Git metadata (commits, branches)
    - Faster than API-based sources for large repos
    """

    def __init__(
        self,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: Optional[AirweaveHttpClient] = None,
    ):
        """Initialize the local git source."""
        super().__init__(auth=auth, logger=logger, http_client=http_client)
        self._repo_path: Optional[str] = None
        self._branch: str = "main"
        self._follow_symlinks: bool = False
        self._max_file_size: int = 10 * 1024 * 1024  # 10MB
        self._included_extensions: List[str] = []

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: LocalGitConfig,
    ) -> "LocalGitSource":
        """Create a new local git source instance."""
        instance = cls(auth=auth, logger=logger, http_client=None)

        # Map host path to container path in Docker environment (config-driven)
        repo_path = cls._map_host_path_to_container(config.repo_path, logger=logger)

        instance._repo_path = repo_path
        instance._branch = config.branch or "main"
        instance._follow_symlinks = config.follow_symlinks
        return instance

    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field for local git source."""
        return "last_modified_at"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate if the given cursor field is valid for local git source."""
        valid_field = self.get_default_cursor_field()
        if cursor_field != valid_field:
            error_msg = (
                f"Invalid cursor field '{cursor_field}' for Local Git source. "
                f"Local Git source requires '{valid_field}' as the cursor field."
            )
            self.logger.warning(error_msg)
            raise ValueError(error_msg)

    async def validate(self) -> None:
        """Validate that this source is reachable and credentials are usable.

        For LocalGit, validation checks if repository path exists and is a valid git repository.
        """
        if not self._repo_path:
            raise ValueError("Repository path not configured")

        # Check if path exists
        if not os.path.exists(self._repo_path):
            raise ValueError(f"Repository path does not exist: {self._repo_path}")

        # Check if it's a git repository
        try:
            self._ensure_safe_directory()
            from git import Repo as GitRepo
            GitRepo(self._repo_path)
        except Exception as e:
            raise ValueError(f"Invalid git repository at {self._repo_path}: {e}")

    async def generate_entities(
        self,
        cursor: Optional[Any] = None,
        files: Optional[FileService] = None,
        node_selections: Optional[Any] = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from local git repository.

        Args:
            cursor: Sync cursor for incremental updates
            files: FileService for saving files to temp directory
            node_selections: Node selection data for filtering (optional)

        Yields:
            GitHub entities: repository, directories, and code files
        """
        # Import git here to avoid issues when not installed
        try:
            from git import Repo as GitRepo
        except ImportError:
            raise ImportError(
                "GitPython is not installed. Please run: pip install gitpython"
            )

        if not self._repo_path:
            self.logger.error("Repository path not configured")
            return

        try:
            self._ensure_safe_directory()
            repo = GitRepo(self._repo_path)
        except Exception as e:
            self.logger.error(f"Failed to open git repository at {self._repo_path}: {e}")
            return

        self.logger.info(f"Starting sync of local repository: {self._repo_path}")

        # Validate and select branch
        self._validate_and_select_branch(repo)

        # Generate repository entity
        yield await asyncio.to_thread(self._create_repository_entity, repo)

        # Generate file and directory entities
        try:
            async for entity in self._create_file_entities(repo, cursor, files):
                yield entity
        except Exception as e:
            self.logger.error(f"Error during file entity generation: {e}")
            raise

    def _validate_and_select_branch(self, repo: Any) -> None:
        """Validate and select the specified branch."""
        if not self._branch:
            # Use default branch
            self._branch = repo.active_branch.name
            self.logger.info(f"Using default branch: {self._branch}")
            return

        # Check if branch exists
        branch_names = [h.name for h in repo.heads]
        if self._branch not in branch_names:
            available = ", ".join(branch_names[:5])
            self.logger.warning(
                f"Branch '{self._branch}' not found. Available branches: {available}"
            )
            self._branch = repo.active_branch.name

    async def _create_file_entities(
        self,
        repo: Any,
        cursor: Optional[Any] = None,
        file_service: Optional[FileService] = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Create file and directory entities from repository.

        Args:
            repo: GitPython repository object
            cursor: Sync cursor for incremental updates
            file_service: FileService for saving files to temp directory

        Yields:
            GitHub entities: directories and code files
        """
        # Get last modified timestamp from cursor if available
        last_modified_at = None
        if cursor and hasattr(cursor, "value"):
            try:
                last_modified_at = datetime.fromisoformat(cursor.value)
            except (ValueError, AttributeError):
                pass

        # Walk through repository filesystem
        for root, dirs, filenames in os.walk(self._repo_path):
            # Skip .git directory (git metadata should not be indexed)
            dirs[:] = [d for d in dirs if d != ".git"]

            # Check if we should follow symlinks
            if not self._follow_symlinks:
                dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]

            # Get relative path
            rel_path = os.path.relpath(root, self._repo_path)

            # Create directory entity
            if rel_path != ".":
                dir_entity = await asyncio.to_thread(
                    self._create_directory_entity, rel_path, repo
                )
                yield dir_entity

            # Process files
            for file in filenames:
                file_path = os.path.join(root, file)
                file_rel_path = os.path.relpath(file_path, self._repo_path)

                # Skip symlinks if not following
                if not self._follow_symlinks and os.path.islink(file_path):
                    continue

                # Skip files that are too large
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > self._max_file_size:
                        self.logger.debug(
                            f"Skipping large file: {file_rel_path} ({file_size} bytes)"
                        )
                        continue
                except OSError:
                    continue

                # Read file content for text detection and processing
                try:
                    with open(file_path, "rb") as f:
                        file_content = f.read(16384)  # Read first 16KB for text detection
                except OSError:
                    continue

                # Skip non-text files
                if not is_text_file(file_path, file_size, file_content):
                    continue

                # Check if file was modified since last sync
                if last_modified_at:
                    try:
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_mtime <= last_modified_at:
                            self.logger.debug(
                                f"Skipping unchanged file: {file_rel_path}"
                            )
                            continue
                    except OSError:
                        continue

                # Create code file entity
                try:
                    file_entity, content_bytes = await asyncio.to_thread(
                        self._create_code_file_entity,
                        file_path,
                        file_rel_path,
                        repo,
                    )

                    if file_service:
                        await file_service.save_bytes(
                            entity=file_entity,
                            content=content_bytes,
                            filename_with_extension=file_rel_path,
                            logger=self.logger,
                        )

                        if not file_entity.local_path:
                            raise ValueError(
                                f"Save failed - no local path set for {file_entity.name}"
                            )
                    yield file_entity
                except FileSkippedException as e:
                    self.logger.debug(f"Skipping file: {e.reason}")
                except Exception as e:
                    self.logger.warning(
                        f"Failed to create entity for file {file_rel_path}: {e}"
                    )
                    continue

    def _create_repository_entity(self, repo: Any) -> GitHubRepositoryEntity:
        """Create repository entity from git repository.

        Args:
            repo: GitPython repository object

        Returns:
            GitHubRepositoryEntity
        """
        latest_commit = repo.commit()

        # Detect primary language
        language = self._detect_primary_language(repo)

        repo_path = self._repo_path or ""
        repo_name = Path(repo_path).name

        return GitHubRepositoryEntity(
            repo_id=hash(repo_path) % (2**31),  # Use hash as ID
            name=repo_name,
            created_at=datetime.fromtimestamp(latest_commit.authored_date),
            updated_at=datetime.fromtimestamp(latest_commit.committed_date),
            full_name=repo_path,
            default_branch=self._branch,
            language=language,
            size=self._get_repo_size(repo_path),
            fork=False,  # Local repositories are not forks
            forks_count=None,
            open_issues_count=None,
            stars_count=None,
            watchers_count=None,
            description=f"Local repository: {repo_name}",
            breadcrumbs=[],
        )

    def _create_directory_entity(
        self, rel_path: str, repo: Any
    ) -> GitHubDirectoryEntity:
        """Create directory entity.

        Args:
            rel_path: Relative path to directory
            repo: GitPython repository object

        Returns:
            GitHubDirectoryEntity
        """
        path_parts = rel_path.split("/") if rel_path != "." else []
        dir_name = path_parts[-1] if path_parts else Path(self._repo_path).name

        repo_name = Path(self._repo_path).name

        return GitHubDirectoryEntity(
            full_path=f"{repo_name}/{rel_path}",
            path=rel_path,
            name=dir_name,
            repo_name=repo_name,
            repo_owner="local",  # Local repositories don't have owners
            branch=self._branch,
            breadcrumbs=self._build_breadcrumbs(rel_path),
        )

    def _create_code_file_entity(
        self, file_path: str, file_rel_path: str, repo: Any
    ) -> tuple[GitHubCodeFileEntity, bytes]:
        """Create code file entity.

        Args:
            file_path: Absolute path to file
            file_rel_path: Relative path to file
            repo: GitPython repository object
        Returns:
            A tuple of (GitHubCodeFileEntity, UTF-8 encoded file bytes)
        """
        # Read file content
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content_text = f.read()
        except IOError as e:
            raise IOError(f"Failed to read file {file_path}: {e}")

        # Get Git metadata
        try:
            commits = list(repo.iter_commits(paths=file_rel_path, max_count=1))
            sha = commits[0].hexsha if commits else "unknown"
        except Exception:
            sha = "unknown"

        # Detect language
        language = self._detect_language_from_extension(file_rel_path)

        # Calculate line count (matching GitHub Source)
        line_count = content_text.count("\n") + 1

        # Detect MIME type (matching GitHub Source)
        mime_type = mimetypes.guess_type(file_rel_path)[0] or "text/plain"
        file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

        repo_name = Path(self._repo_path).name

        file_entity = GitHubCodeFileEntity(
            breadcrumbs=self._build_breadcrumbs(file_rel_path),
            full_path=f"{repo_name}/{file_rel_path}",
            name=Path(file_rel_path).name,
            branch=self._branch,
            url=f"file://{file_path}",
            size=os.path.getsize(file_path),
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,  # Will be set by FileService.save_bytes()
            repo_name=repo_name,
            path_in_repo=file_rel_path,
            repo_owner="local",
            language=language,
            commit_id=sha,
            html_url=f"file://{file_path}",
            sha=sha,
            line_count=line_count,
            is_binary=False,
        )

        return file_entity, content_text.encode("utf-8")

    def _build_breadcrumbs(self, rel_path: str) -> List[Breadcrumb]:
        """Build breadcrumbs from relative path.

        Args:
            rel_path: Relative path to file/directory

        Returns:
            List of breadcrumb entities
        """
        if not rel_path or rel_path == ".":
            return []

        parts = rel_path.split("/")
        breadcrumbs = []

        for i, part in enumerate(parts):
            breadcrumb_path = "/".join(parts[: i + 1])
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=breadcrumb_path,
                    name=part,
                    entity_type="directory" if i < len(parts) - 1 else "file",
                )
            )

        return breadcrumbs

    def _detect_language_from_extension(self, file_path: str) -> str:
        """Detect programming language from file extension.

        Args:
            file_path: Path to file

        Returns:
            Programming language name
        """
        ext = Path(file_path).suffix.lower()
        return get_language_for_extension(ext)

    def _detect_primary_language(self, repo: Any) -> Optional[str]:
        """Detect primary language from repository files.

        Args:
            repo: GitPython repository object

        Returns:
            Primary programming language
        """
        language_counts: Dict[str, int] = {}

        # Count files by language
        for root, dirs, files in os.walk(self._repo_path):
            # Skip .git directory (git metadata should not be indexed)
            dirs[:] = [d for d in dirs if d != ".git"]

            for file in files:
                file_path = os.path.join(root, file)

                # Skip non-text files
                if not is_text_file(file_path):
                    continue

                language = self._detect_language_from_extension(file_path)
                if language:
                    language_counts[language] = language_counts.get(language, 0) + 1

        # Find most common language
        if language_counts:
            return max(language_counts, key=language_counts.get)

        return None

    def _get_repo_size(self, repo_path: str) -> int:
        """Calculate repository size in KB.

        Args:
            repo_path: Path to repository

        Returns:
            Size in kilobytes
        """
        total_size = 0

        try:
            for root, dirs, files in os.walk(repo_path):
                # Skip .git directory
                if ".git" in dirs:
                    dirs.remove(".git")

                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except OSError:
                        continue
        except Exception:
            pass

        return total_size // 1024  # Convert to KB

    def _ensure_safe_directory(self) -> None:
        """Ensure mounted host repos are trusted by git in containerized environments."""
        if not self._repo_path:
            return

        # Only auto-trust configured mounted prefixes inside Docker.
        if not os.path.exists("/.dockerenv"):
            return
        mapped_prefixes = tuple(container for _, container in settings.local_git_mount_map_pairs)
        if mapped_prefixes and not self._path_under_prefixes(self._repo_path, mapped_prefixes):
            return

        try:
            get_result = subprocess.run(
                ["git", "config", "--global", "--get-all", "safe.directory"],
                capture_output=True,
                text=True,
                check=False,
            )
            configured = set(get_result.stdout.splitlines())
            if self._repo_path in configured:
                return

            subprocess.run(
                ["git", "config", "--global", "--add", "safe.directory", self._repo_path],
                capture_output=True,
                text=True,
                check=True,
            )
            self.logger.info("Added git safe.directory for local repo: %s", self._repo_path)
        except Exception as e:
            # Non-fatal: GitRepo(...) below will raise a clearer validation error if needed.
            self.logger.warning("Failed to configure git safe.directory for %s: %s", self._repo_path, e)

    @classmethod
    def _map_host_path_to_container(cls, host_path: str, *, logger: ContextualLogger) -> str:
        """Map configured host path prefixes to container prefixes (longest-prefix match)."""
        if not (os.path.exists("/.dockerenv") and host_path):
            return host_path

        normalized_host_path = cls._normalize_prefix(host_path)
        best_match: tuple[str, str] | None = None
        for host_prefix, container_prefix in settings.local_git_mount_map_pairs:
            if cls._path_under_prefixes(normalized_host_path, (host_prefix,)):
                if best_match is None or len(host_prefix) > len(best_match[0]):
                    best_match = (host_prefix, container_prefix)

        if not best_match:
            return normalized_host_path

        host_prefix, container_prefix = best_match
        if normalized_host_path == host_prefix:
            mapped_path = container_prefix
        else:
            suffix = normalized_host_path[len(host_prefix) :].lstrip("/")
            mapped_path = f"{container_prefix}/{suffix}"

        logger.info("Mapped host path to container path: %s -> %s", host_path, mapped_path)
        return mapped_path

    @staticmethod
    def _normalize_prefix(path: str) -> str:
        """Normalize a POSIX path and remove trailing slash."""
        normalized = os.path.normpath(path.strip())
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized

    @staticmethod
    def _path_under_prefixes(path: str, prefixes: tuple[str, ...]) -> bool:
        """Return True if path equals prefix or is under any prefix."""
        return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)