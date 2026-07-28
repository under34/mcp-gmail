"""User-private locations for persistent application data."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir


@dataclass(frozen=True)
class AppPaths:
    """Filesystem locations that must remain outside the source checkout."""

    root: Path
    oauth_token: Path
    sqlite: Path
    digests: Path
    filters: Path


def get_app_paths(data_dir: Path | None = None) -> AppPaths:
    """Create and return private, per-user locations for local application state."""
    root = (data_dir or Path(user_data_dir("gmail-mcp", appauthor=False))).expanduser().resolve()
    _ensure_outside_git_checkout(root)
    oauth_dir = root / "oauth"
    database_dir = root / "database"
    digests_dir = root / "digests"
    filters_dir = root / "filters"

    for directory in (root, oauth_dir, database_dir, digests_dir, filters_dir):
        _create_private_directory(directory)

    return AppPaths(
        root=root,
        oauth_token=oauth_dir / "token.json",
        sqlite=database_dir / "gmail-mcp.sqlite3",
        digests=digests_dir,
        filters=filters_dir,
    )


def restrict_file_permissions(path: Path) -> None:
    """Restrict a token or credential file where POSIX permissions are available."""
    if os.name == "posix" and path.exists():
        if stat.S_ISLNK(path.lstat().st_mode):
            raise ValueError("Refusing to change permissions through a symbolic link.")
        path.chmod(0o600)


def _restrict_directory_permissions(path: Path) -> None:
    if os.name == "posix":
        path.chmod(0o700)


def _create_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("Application data directories must not be symbolic links.")
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Application data directories must not be symbolic links.")
    _restrict_directory_permissions(path)


def _ensure_outside_git_checkout(root: Path) -> None:
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists() and (ancestor / "pyproject.toml").is_file():
            raise ValueError("Application data directory must be outside a Git checkout.")
