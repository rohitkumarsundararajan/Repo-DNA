"""Tiny shared helper: display a path relative to a repo root."""

from __future__ import annotations

import os
from pathlib import Path


def display_path(path: Path, root: str | os.PathLike | None) -> str:
    if root is not None:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.as_posix()