"""Disposable, locked-down Docker containers for handling untrusted repositories.

One job step = one short-lived container started from the prebuilt sandbox image
(`infra/sandbox.Dockerfile`). The container runs as a non-root user with no Linux
capabilities, memory/CPU/process/file-size limits and a hard time limit, and is
always removed afterwards. Results leave the container as a tar stream
(`get_archive`), so no folder is ever shared between the worker and the sandbox.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence

import docker
from docker.errors import DockerException, ImageNotFound
from docker.types import Ulimit

from ..consumer import config
from .archive import ExtractResult, extract_tar_stream

log = logging.getLogger("repodna.sandbox")

WORKDIR = "/work"
POLL_INTERVAL_SECONDS = 0.5
LOG_TAIL_LINES = 15
MAX_OUTPUT_CHARS = 400


class SandboxError(RuntimeError):
    """The sandbox could not be started or the command inside it failed."""


class SandboxTimeoutError(SandboxError):
    """The command did not finish inside the time limit and was killed."""


class Sandbox:
    """Runs one command at a time in a throw-away container."""

    def __init__(
        self,
        docker_client: docker.DockerClient | None = None,
        image: str | None = None,
        timeout: int | None = None,
        memory: str | None = None,
        cpus: float | None = None,
        pids_limit: int | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = docker_client
        self.image = image or config.SANDBOX_IMAGE
        self.timeout = timeout if timeout is not None else config.SANDBOX_TIMEOUT_SECONDS
        self.memory = memory or config.SANDBOX_MEMORY
        self.cpus = cpus if cpus is not None else config.SANDBOX_CPUS
        self.pids_limit = pids_limit if pids_limit is not None else config.SANDBOX_PIDS_LIMIT
        self._clock = clock
        self._sleep = sleep

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                self._client = docker.from_env()
            except DockerException as error:
                raise SandboxError(f"Cannot reach the Docker engine: {error}") from error
        return self._client

    def ensure_image(self) -> None:
        """Fail fast, with a clear message, when the sandbox image is missing."""
        try:
            self.client.images.get(self.image)
        except ImageNotFound as error:
            raise SandboxError(
                f"Sandbox image '{self.image}' not found. "
                "Build it with: docker compose build sandbox-image"
            ) from error
        except DockerException as error:
            raise SandboxError(f"Cannot check the sandbox image: {error}") from error

    @contextmanager
    def run(
        self,
        command: Sequence[str],
        environment: Mapping[str, str] | None = None,
    ) -> Iterator["docker.models.containers.Container"]:
        """Run `command` to completion; yield the stopped container for copying files out.

        Raises SandboxTimeoutError after `timeout` seconds and SandboxError on a
        non-zero exit. The container is always removed on exit.
        """
        container = None
        try:
            try:
                container = self.client.containers.run(
                    self.image,
                    command=list(command),
                    detach=True,
                    working_dir=WORKDIR,
                    environment=dict(environment or {}),
                    mem_limit=self.memory,
                    memswap_limit=self.memory,  # no swap
                    nano_cpus=int(self.cpus * 1_000_000_000),
                    pids_limit=self.pids_limit,
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges"],
                    tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
                    ulimits=[
                        Ulimit(
                            name="fsize",
                            soft=config.MAX_REPO_SIZE_MB * 1024 * 1024,
                            hard=config.MAX_REPO_SIZE_MB * 1024 * 1024,
                        )
                    ],
                    labels={"repodna.role": "sandbox"},
                )
            except DockerException as error:
                raise SandboxError(f"Unable to start the repository sandbox: {error}") from error

            exit_code = self._wait(container)
            if exit_code != 0:
                raise SandboxError(self._failure_message(container, exit_code))
            yield container
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except DockerException:
                    log.warning("could not remove sandbox container %s", container.short_id)

    def copy_out(
        self,
        container,
        source_path: str,
        destination: str | Path,
        *,
        max_files: int | None = None,
        max_total_size: int | None = None,
    ) -> ExtractResult:
        """Copy a folder out of the container into `destination` (safely)."""
        try:
            chunks, _stat = container.get_archive(source_path)
        except DockerException as error:
            raise SandboxError(f"Could not read {source_path} from the sandbox: {error}") from error
        return extract_tar_stream(
            chunks,
            destination,
            max_files=max_files if max_files is not None else config.MAX_FILES,
            max_total_size=(
                max_total_size
                if max_total_size is not None
                else config.MAX_REPO_SIZE_MB * 1024 * 1024
            ),
        )

    # -- internals -----------------------------------------------------------

    def _wait(self, container) -> int:
        deadline = self._clock() + self.timeout
        while True:
            try:
                container.reload()
            except DockerException as error:
                raise SandboxError(f"Lost contact with the sandbox container: {error}") from error
            state = container.attrs.get("State", {})
            if state.get("Status") in ("exited", "dead"):
                return int(state.get("ExitCode", 1))
            if self._clock() >= deadline:
                try:
                    container.kill()
                except DockerException:
                    pass
                raise SandboxTimeoutError(
                    f"The sandbox command took longer than {self.timeout} seconds and was stopped"
                )
            self._sleep(POLL_INTERVAL_SECONDS)

    def _failure_message(self, container, exit_code: int) -> str:
        try:
            raw = container.logs(stdout=True, stderr=True, tail=LOG_TAIL_LINES)
            output = raw.decode("utf-8", errors="replace").strip()
        except DockerException:
            output = ""
        output = output[-MAX_OUTPUT_CHARS:]
        return f"Sandbox command failed (exit {exit_code}): {output}" if output else (
            f"Sandbox command failed (exit {exit_code})"
        )
