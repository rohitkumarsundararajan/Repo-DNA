"""Parse all files in a repository across CPU cores.

Each file is parsed independently (spec section 5), so a process pool scales
close to linearly with core count. Parsing runs in worker processes; nothing
here executes repository content.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import Executor, ProcessPoolExecutor, as_completed
from math import ceil
from pathlib import Path
from typing import Iterable

from ..detect.language import IGNORED_DIRS
from .models import ParsedFile
from .parser import EXTENSION_GRAMMARS, parse_file

logger = logging.getLogger(__name__)

# Chunks are oversubscribed relative to worker count so no single slow file
# (or uneven chunk) stalls a whole worker while others sit idle.
CHUNK_OVERSUBSCRIPTION = 4


def _discover_files(root: Path) -> list[Path]:
    """Supported source files under `root`, ignored dirs and symlinks pruned."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.suffix.lower() in EXTENSION_GRAMMARS and not path.is_symlink():
                found.append(path)
    return found


def _chunk_paths(paths: list[str], workers: int) -> list[list[str]]:
    """Split `paths` into chunks for a pool of `workers` processes."""
    if not paths:
        return []
    target = max(1, min(len(paths), workers * CHUNK_OVERSUBSCRIPTION))
    size = ceil(len(paths) / target)
    return [paths[i : i + size] for i in range(0, len(paths), size)]


def _parse_chunk(
    paths: list[str], root: str
) -> list[tuple[str, ParsedFile | None, str | None]]:
    """Parse each path in a chunk. Runs in a worker process.

    Returns one (path, parsed, error) triple per path: `error` is None on
    success (including a deliberate skip, where `parsed` is also None), and
    the exception's repr on an unexpected failure. Never raises, so one bad
    file can't take a whole chunk down with it.
    """
    results = []
    for path in paths:
        try:
            parsed = parse_file(path, root=root)
        except Exception as exc:  # pragma: no cover - parse_file already guards this
            results.append((path, None, repr(exc)))
        else:
            results.append((path, parsed, None))
    return results


def parse_repository(
    root: str | os.PathLike,
    paths: Iterable[str | os.PathLike] | None = None,
    max_workers: int | None = None,
    executor_cls: type[Executor] = ProcessPoolExecutor,
) -> list[ParsedFile]:
    """Parse every file under `root` in parallel and return the successes.

    If `paths` is omitted, the tree is walked for files with a supported
    extension (the same ignored directories as language/framework
    detection). Otherwise only the given paths are parsed.

    `max_workers` defaults to `os.cpu_count()` (or 1 if that's unknown).
    `executor_cls` defaults to `ProcessPoolExecutor`; tests can substitute
    `ThreadPoolExecutor` to exercise this function in-process.

    Files skipped by `parse_file` itself (unsupported type, binary,
    oversized, symlink, unreadable) are silently absent from the result.
    Files that raise unexpectedly, and chunks lost to a worker crash, are
    logged as warnings and also absent; nothing here re-raises. The
    returned list is sorted by `ParsedFile.path` for a deterministic order,
    independent of completion order.
    """
    root = Path(root).resolve()
    path_list = (
        [str(p) for p in _discover_files(root)]
        if paths is None
        else [str(p) for p in paths]
    )
    if not path_list:
        return []

    workers = max_workers or os.cpu_count() or 1
    chunks = _chunk_paths(path_list, workers)

    parsed_files: list[ParsedFile] = []
    failed = 0

    with executor_cls(max_workers=workers) as executor:
        futures = {
            executor.submit(_parse_chunk, chunk, str(root)): chunk for chunk in chunks
        }
        for future in as_completed(futures):
            chunk = futures[future]
            try:
                chunk_results = future.result()
            except Exception:
                logger.error(
                    "worker failed while parsing a chunk of %d files; skipping them: %s",
                    len(chunk),
                    chunk,
                    exc_info=True,
                )
                failed += len(chunk)
                continue

            for path, parsed, error in chunk_results:
                if error is not None:
                    logger.warning("failed to parse %s: %s", path, error)
                    failed += 1
                elif parsed is not None:
                    parsed_files.append(parsed)

    logger.info(
        "parsed %d/%d files (%d failed)", len(parsed_files), len(path_list), failed
    )
    parsed_files.sort(key=lambda pf: pf.path)
    return parsed_files