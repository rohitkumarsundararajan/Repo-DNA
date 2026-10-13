"""Clone a public repository inside the sandbox and hand the files to the worker."""

from __future__ import annotations

import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from ..consumer import config
from .container import Sandbox, SandboxError, SandboxTimeoutError

log = logging.getLogger("repodna.sandbox")

REPO_DIR_IN_SANDBOX = "/work/repository"

# The URL is passed as an argument ($1), never spliced into the shell string, and
# "--" stops it from being read as a git option. .git is dropped before copying out.
_CLONE_SCRIPT = (
    "set -e; "
    f'git clone --depth 1 --single-branch --no-tags -- "$1" {REPO_DIR_IN_SANDBOX}; '
    f"rm -rf {REPO_DIR_IN_SANDBOX}/.git"
)

_CLONE_ENV = {
    "HOME": "/home/sandbox",
    "GIT_TERMINAL_PROMPT": "0",  # never wait for a password
    "GIT_ASKPASS": "/bin/true",
}

PUBLIC_ONLY_MESSAGE = "Only public https GitHub and GitLab repository URLs can be analyzed"


def validate_repo_url(url: str, allowed_hosts: frozenset[str] | None = None) -> str:
    """Return the URL if it is a plain public https URL on an allowed host."""
    allowed = allowed_hosts if allowed_hosts is not None else config.ALLOWED_GIT_HOSTS
    if not isinstance(url, str) or not url or url.startswith("-") or any(c.isspace() for c in url):
        raise ValueError(PUBLIC_ONLY_MESSAGE)
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if (
        parsed.scheme != "https"
        or host not in allowed
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError(PUBLIC_ONLY_MESSAGE)
    return url


def _friendly_clone_error(error: SandboxError) -> str:
    if isinstance(error, SandboxTimeoutError):
        return (
            f"Cloning took longer than {config.SANDBOX_TIMEOUT_SECONDS} seconds; "
            "the repository may be too large"
        )
    text = str(error).lower()
    if any(
        marker in text
        for marker in (
            "terminal prompts disabled",
            "could not read username",
            "repository not found",
            "authentication failed",
            "not found",
        )
    ):
        return "Repository not found, or it is private. Only public repositories can be analyzed"
    if "could not resolve host" in text or "unable to access" in text:
        return "The repository host could not be reached; try again later"
    return str(error)


@contextmanager
def clone_repo(
    repository_url: str,
    *,
    docker_client=None,
    dockerfile=None,  # accepted for backward compatibility; the image is prebuilt now
    sandbox: Sandbox | None = None,
) -> Iterator[Path]:
    """Yield a shallow single-branch checkout and remove it when the job ends."""
    url = validate_repo_url(repository_url)
    sandbox = sandbox or Sandbox(docker_client=docker_client)
    workspace = Path(tempfile.mkdtemp(prefix="repodna-clone-", dir=config.WORK_DIR))
    try:
        try:
            with sandbox.run(
                ["sh", "-c", _CLONE_SCRIPT, "sh", url], environment=_CLONE_ENV
            ) as container:
                sandbox.copy_out(container, REPO_DIR_IN_SANDBOX, workspace / "repository")
        except SandboxError as error:
            raise SandboxError(_friendly_clone_error(error)) from error
        yield workspace / "repository"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


clone_repository = clone_repo
