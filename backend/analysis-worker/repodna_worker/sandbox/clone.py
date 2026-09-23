"""Clone a repository inside a resource-limited disposable sandbox."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .container import Sandbox


@contextmanager
def clone_repo(
    repository_url: str,
    *,
    docker_client=None,
    dockerfile: str | Path | None = None,
) -> Iterator[Path]:
    """Yield a shallow single-branch clone and remove it when the job ends."""
    with Sandbox(docker_client=docker_client, dockerfile=dockerfile) as sandbox:
        sandbox.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--single-branch",
                repository_url,
                "/workspace/repository",
            ]
        )
        yield sandbox.workspace / "repository"


clone_repository = clone_repo
