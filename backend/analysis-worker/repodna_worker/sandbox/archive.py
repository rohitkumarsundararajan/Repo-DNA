"""Safe extraction of a tar stream coming out of the sandbox container.

The sandbox holds untrusted data, so nothing from it is trusted here: names are
checked for traversal, only plain files and folders are written, links and device
files are skipped, and file-count and total-size ceilings are enforced while
streaming (a hostile repository cannot fill the disk).
"""

from __future__ import annotations

import io
import logging
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from .resource_limits import RepositoryLimitError

log = logging.getLogger("repodna.sandbox")

COPY_CHUNK_BYTES = 1024 * 1024


class UnsafeArchiveError(ValueError):
    """Raised when an archive entry tries to escape the destination."""


@dataclass(frozen=True)
class ExtractResult:
    files: int
    bytes_written: int
    skipped: int  # symlinks, hardlinks, devices and other non-regular entries


class _ChunkReader(io.RawIOBase):
    """File-like wrapper around an iterator of byte chunks (docker get_archive)."""

    def __init__(self, chunks: Iterable[bytes]) -> None:
        self._chunks = iter(chunks)
        self._buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, target) -> int:
        while not self._buffer:
            try:
                self._buffer = next(self._chunks)
            except StopIteration:
                return 0
        size = min(len(target), len(self._buffer))
        target[:size] = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return size


def _relative_path(name: str, strip_components: int) -> PurePosixPath | None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise UnsafeArchiveError(f"Archive path is not allowed: {name!r}")
    parts = [part for part in path.parts if part != "."]
    parts = parts[strip_components:]
    if not parts:
        return None
    return PurePosixPath(*parts)


def extract_tar_stream(
    chunks: Iterable[bytes],
    destination: str | Path,
    *,
    max_files: int,
    max_total_size: int,
    strip_components: int = 1,
) -> ExtractResult:
    """Extract a (possibly huge) tar stream into `destination` safely.

    `strip_components` removes the leading folder docker adds (for example
    `repository/`). Anything under a `.git` folder is ignored.
    """
    dest = Path(destination).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    files = 0
    total = 0
    skipped = 0

    with tarfile.open(fileobj=_ChunkReader(chunks), mode="r|") as archive:
        for member in archive:
            relative = _relative_path(member.name, strip_components)
            if relative is None or ".git" in relative.parts:
                continue

            target = (dest / relative).resolve()
            if target != dest and dest not in target.parents:
                raise UnsafeArchiveError(f"Archive path escapes destination: {member.name!r}")

            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isreg():
                skipped += 1
                continue

            files += 1
            if files > max_files:
                raise RepositoryLimitError(f"repository file count exceeds limit ({max_files})")
            if total + member.size > max_total_size:
                raise RepositoryLimitError(
                    f"repository size exceeds limit ({max_total_size} bytes)"
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:  # pragma: no cover - isreg() guarantees a file object
                skipped += 1
                continue
            with source, target.open("wb") as output:
                while True:
                    block = source.read(COPY_CHUNK_BYTES)
                    if not block:
                        break
                    total += len(block)
                    if total > max_total_size:
                        raise RepositoryLimitError(
                            f"repository size exceeds limit ({max_total_size} bytes)"
                        )
                    output.write(block)

    if skipped:
        log.info("skipped %d links/special files while extracting", skipped)
    return ExtractResult(files=files, bytes_written=total, skipped=skipped)
