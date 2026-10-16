"""Repository resource ceilings applied before analysis begins."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from ..consumer import config


class RepositoryLimitError(ValueError):
    """Raised when a repository exceeds a configured resource ceiling."""


def validate_repository(
    root: str | os.PathLike,
    *,
    max_files: int = config.MAX_FILES,
    max_file_size: int = config.MAX_FILE_SIZE_MB * 1024 * 1024,
    max_total_size: int = config.MAX_REPO_SIZE_MB * 1024 * 1024,
) -> None:
    """Reject repositories exceeding file-count, per-file, or total-byte limits.

    Git metadata is excluded because it is not part of the checked-out source.
    Symlinks are counted but never followed.
    """
    if min(max_files, max_file_size, max_total_size) < 0:
        raise ValueError("repository limits must be non-negative")

    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError(f"repository path is not a directory: {root_path}")

    pending = [root_path]
    file_count = 0
    total_size = 0
    while pending:
        directory = pending.pop()
        try:
            entries = os.scandir(directory)
            with entries:
                for entry in entries:
                    if entry.name == ".git" and entry.is_dir(follow_symlinks=False):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                        continue

                    file_count += 1
                    if file_count > max_files:
                        raise RepositoryLimitError(
                            f"repository file count exceeds limit ({max_files})"
                        )
                    try:
                        entry_stat = entry.stat(follow_symlinks=False)
                    except OSError as error:
                        raise RepositoryLimitError(
                            f"unable to inspect repository file: {entry.path}"
                        ) from error
                    if not stat.S_ISREG(entry_stat.st_mode):
                        continue
                    if entry_stat.st_size > max_file_size:
                        raise RepositoryLimitError(
                            f"repository file exceeds size limit ({max_file_size} bytes): "
                            f"{entry.path}"
                        )
                    total_size += entry_stat.st_size
                    if total_size > max_total_size:
                        raise RepositoryLimitError(
                            f"repository size exceeds limit ({max_total_size} bytes)"
                        )
        except OSError as error:
            raise RepositoryLimitError(
                f"unable to inspect repository directory: {directory}"
            ) from error