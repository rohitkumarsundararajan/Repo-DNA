"""Disposable Docker execution for repository analysis jobs."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Iterable

import docker
from docker.errors import DockerException


SANDBOX_TIMEOUT_SECONDS = 120
SANDBOX_MEMORY = "1g"
SANDBOX_CPUS = 1_000_000_000


class SandboxError(RuntimeError):
    """Raised when a sandbox job cannot be started or completed."""


class Sandbox:
    """Run commands in a disposable container with a temporary workspace."""

    def __init__(
        self,
        docker_client: docker.DockerClient | None = None,
        dockerfile: str | Path | None = None,
        timeout: int = SANDBOX_TIMEOUT_SECONDS,
    ) -> None:
        self.client = docker_client or docker.from_env()
        self.dockerfile = Path(dockerfile or Path(__file__).parents[4] / "infra" / "sandbox.Dockerfile")
        self.timeout = timeout
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._container = None

    def __enter__(self) -> "Sandbox":
        self._temporary_directory = tempfile.TemporaryDirectory(prefix="repodna-sandbox-")
        try:
            image, _ = self.client.images.build(
                path=str(self.dockerfile.parent),
                dockerfile=self.dockerfile.name,
                tag="repodna-sandbox:local",
                rm=True,
            )
            self._container = self.client.containers.run(
                image.id,
                command=["sleep", str(self.timeout)],
                detach=True,
                auto_remove=True,
                mem_limit=SANDBOX_MEMORY,
                nano_cpus=SANDBOX_CPUS,
                volumes={
                    self._temporary_directory.name: {
                        "bind": "/workspace",
                        "mode": "rw",
                    }
                },
                working_dir="/workspace",
            )
        except (DockerException, OSError) as error:
            self.close()
            raise SandboxError("Unable to start the repository sandbox") from error
        return self

    @property
    def workspace(self) -> Path:
        if self._temporary_directory is None:
            raise SandboxError("The sandbox has not been entered")
        return Path(self._temporary_directory.name)

    def run(self, command: Iterable[str]) -> str:
        """Execute a command and fail if it exits non-zero or times out."""
        if self._container is None:
            raise SandboxError("The sandbox has not been entered")
        try:
            result = self._container.exec_run(list(command), workdir="/workspace")
            if result.exit_code != 0:
                output = result.output.decode("utf-8", errors="replace")
                raise SandboxError(f"Sandbox command failed ({result.exit_code}): {output}")
            return result.output.decode("utf-8", errors="replace")
        except DockerException as error:
            raise SandboxError("Sandbox command timed out or could not be executed") from error

    def close(self) -> None:
        if self._container is not None:
            try:
                self._container.kill()
            except DockerException:
                pass
            self._container = None
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
            self._temporary_directory = None

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
