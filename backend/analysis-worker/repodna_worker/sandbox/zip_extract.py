"""ZIP extraction with traversal and resource exhaustion protections."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path


DEFAULT_MAX_TOTAL_SIZE = 512 * 1024 * 1024
DEFAULT_MAX_FILES = 10_000


class UnsafeZipError(ValueError):
    """Raised when a ZIP archive violates extraction safety limits."""


def _safe_member_path(destination: Path, member_name: str) -> Path:
    if not member_name or "\x00" in member_name:
        raise UnsafeZipError("ZIP member has an invalid path")
    member_path = Path(member_name)
    if member_path.is_absolute() or member_path.drive:
        raise UnsafeZipError(f"Absolute ZIP path is not allowed: {member_name}")
    target = (destination / member_path).resolve()
    try:
        target.relative_to(destination)
    except ValueError as error:
        raise UnsafeZipError(f"ZIP path escapes destination: {member_name}") from error
    return target


def extract_zip(
    archive: str | Path,
    destination: str | Path,
    *,
    max_total_size: int = DEFAULT_MAX_TOTAL_SIZE,
    max_files: int = DEFAULT_MAX_FILES,
) -> Path:
    """Safely extract an archive, rejecting unsafe entries before writing."""
    if max_total_size < 0 or max_files < 0:
        raise ValueError("ZIP limits must be non-negative")

    destination_path = Path(destination).resolve()
    destination_path.mkdir(parents=True, exist_ok=True)
    total_size = 0
    file_count = 0

    with zipfile.ZipFile(archive) as zip_file:
        entries = zip_file.infolist()
        for info in entries:
            _safe_member_path(destination_path, info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise UnsafeZipError(f"Symbolic links are not allowed: {info.filename}")
            if info.is_dir():
                continue
            file_count += 1
            if file_count > max_files:
                raise UnsafeZipError("ZIP file count limit exceeded")
            total_size += info.file_size
            if total_size > max_total_size:
                raise UnsafeZipError("ZIP uncompressed size limit exceeded")

        for info in entries:
            if info.is_dir():
                continue
            target = _safe_member_path(destination_path, info.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(info) as source, target.open("wb") as output:
                remaining = info.file_size
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise UnsafeZipError(f"Truncated ZIP member: {info.filename}")
                    output.write(chunk)
                    remaining -= len(chunk)
                if source.read(1):
                    raise UnsafeZipError(f"ZIP member grew during extraction: {info.filename}")

    return destination_path
