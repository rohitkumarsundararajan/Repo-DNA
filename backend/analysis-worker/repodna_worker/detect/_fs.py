"""Shared read-only filesystem helpers for detection steps.

Nothing here executes repository content. Files are only opened and read.
"""
"""small shared helper I added, so both modules walk the tree and read files the same way"""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

from .language import IGNORED_DIRS

MAX_MANIFEST_BYTES = 1_000_000

_DEP_SECTIONS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)


def iter_files(root: str | os.PathLike) -> Iterator[Path]:
    """Yield files under `root` in a stable order, skipping ignored dirs and symlinks."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if not path.is_symlink():
                yield path


def read_text(path: Path, max_bytes: int = MAX_MANIFEST_BYTES) -> str | None:
    """Read up to `max_bytes` of a file as text; None if unreadable."""
    try:
        with path.open("rb") as fh:
            return fh.read(max_bytes).decode("utf-8", errors="replace")
    except OSError:
        return None


def package_json_deps(text: str) -> set[str]:
    """Dependency names from a package.json body; empty set if malformed."""
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return set()
    if not isinstance(data, dict):
        return set()
    names: set[str] = set()
    for section in _DEP_SECTIONS:
        deps = data.get(section)
        if isinstance(deps, dict):
            names.update(deps)
    return names