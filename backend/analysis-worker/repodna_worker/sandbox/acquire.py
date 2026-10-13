"""Get the source code for a job onto local disk: Git clone or uploaded ZIP."""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..consumer import config
from .clone import clone_repo
from .zip_extract import UnsafeZipError, extract_zip


@contextmanager
def _extract_upload(zip_path: str) -> Iterator[Path]:
    root = Path(config.ZIP_ROOT).resolve()
    archive = Path(zip_path).resolve()
    # The path comes from the queue; only ever read inside the shared uploads folder.
    if root not in archive.parents:
        raise UnsafeZipError("The ZIP file is outside the uploads folder")
    if not archive.is_file():
        raise FileNotFoundError("The uploaded ZIP file was not found")

    workspace = Path(tempfile.mkdtemp(prefix="repodna-zip-", dir=config.WORK_DIR))
    try:
        extracted = extract_zip(archive, workspace / "source")
        yield _single_top_folder(extracted)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _single_top_folder(path: Path) -> Path:
    """GitHub-style ZIPs wrap everything in one folder; analyze from inside it."""
    entries = [entry for entry in path.iterdir() if entry.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return path


@contextmanager
def acquire_source(job: dict) -> Iterator[Path]:
    """Yield a folder holding the job's source code; it is deleted on exit."""
    source_type = job.get("source_type")
    if source_type == "git":
        with clone_repo(job["repo_url"]) as path:
            yield path
    elif source_type == "zip":
        with _extract_upload(job["zip_path"]) as path:
            yield path
    else:
        raise ValueError(f"unsupported source_type: {source_type!r}")
