"""Sandbox container handling, tested with a fake Docker client (no Docker needed)."""

import io
import tarfile

import pytest
from docker.errors import DockerException, ImageNotFound

from repodna_worker.consumer import config
from repodna_worker.sandbox import clone as clone_module
from repodna_worker.sandbox.clone import clone_repo, validate_repo_url
from repodna_worker.sandbox.container import Sandbox, SandboxError, SandboxTimeoutError


def repo_tar(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(f"repository/{name}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


class FakeContainer:
    short_id = "abc123"

    def __init__(self, exit_code=0, finishes_after=0, logs=b"", tar_bytes=b""):
        self.exit_code = exit_code
        self.finishes_after = finishes_after  # number of reload() calls before it exits
        self._logs = logs
        self._tar = tar_bytes
        self.reloads = 0
        self.killed = False
        self.removed = False
        self.attrs = {"State": {"Status": "running"}}

    def reload(self):
        self.reloads += 1
        if self.reloads > self.finishes_after and not self.killed:
            self.attrs = {"State": {"Status": "exited", "ExitCode": self.exit_code}}

    def kill(self):
        self.killed = True

    def logs(self, **kwargs):
        return self._logs

    def get_archive(self, path):
        return iter([self._tar]), {}

    def remove(self, force=False):
        self.removed = True


class FakeClient:
    def __init__(self, container=None, run_error=None, image_missing=False):
        self.container = container
        self.run_error = run_error
        self.run_kwargs = None
        self.run_args = None
        self.containers = self
        self.images = self
        self._image_missing = image_missing

    def run(self, image, **kwargs):
        if self.run_error:
            raise self.run_error
        self.run_args = (image, kwargs)
        return self.container

    def get(self, name):
        if self._image_missing:
            raise ImageNotFound("nope")


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def make_sandbox(client, timeout=120):
    clock = FakeClock()
    return Sandbox(docker_client=client, image="repodna-sandbox:latest", timeout=timeout,
                   clock=clock, sleep=clock.sleep)


def test_container_is_locked_down_and_removed():
    container = FakeContainer()
    client = FakeClient(container)
    with make_sandbox(client).run(["true"]):
        pass
    image, kwargs = client.run_args
    assert image == "repodna-sandbox:latest"
    assert kwargs["cap_drop"] == ["ALL"]
    assert kwargs["security_opt"] == ["no-new-privileges"]
    assert kwargs["mem_limit"] == kwargs["memswap_limit"]
    assert kwargs["pids_limit"] > 0 and kwargs["nano_cpus"] > 0
    assert kwargs["detach"] is True
    assert "volumes" not in kwargs and "binds" not in kwargs  # nothing shared with the host
    assert container.removed


def test_non_zero_exit_reports_log_tail_and_removes_container():
    container = FakeContainer(exit_code=128, logs=b"fatal: repository not found")
    with pytest.raises(SandboxError, match="exit 128"):
        with make_sandbox(FakeClient(container)).run(["false"]):
            pass
    assert container.removed


def test_timeout_kills_and_removes_container():
    container = FakeContainer(finishes_after=10**6)  # never finishes
    with pytest.raises(SandboxTimeoutError):
        with make_sandbox(FakeClient(container), timeout=5).run(["sleep", "999"]):
            pass
    assert container.killed and container.removed


def test_docker_start_failure_becomes_sandbox_error():
    client = FakeClient(run_error=DockerException("daemon down"))
    with pytest.raises(SandboxError, match="Unable to start"):
        with make_sandbox(client).run(["true"]):
            pass


def test_ensure_image_gives_actionable_message():
    with pytest.raises(SandboxError, match="docker compose build sandbox-image"):
        make_sandbox(FakeClient(image_missing=True)).ensure_image()


# --- clone -------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _work_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORK_DIR", str(tmp_path))


def test_clone_copies_repo_out_and_cleans_up(tmp_path):
    container = FakeContainer(tar_bytes=repo_tar({"app.py": b"x = 1\n"}))
    client = FakeClient(container)
    with clone_repo("https://github.com/pallets/click", sandbox=make_sandbox(client)) as path:
        assert (path / "app.py").read_text() == "x = 1\n"
        kept = path
    assert not kept.exists()
    assert container.removed
    # The URL is an argument, never part of the shell string.
    command = client.run_args[1]["command"]
    assert command[-1] == "https://github.com/pallets/click"
    assert "pallets" not in command[2]


def test_clone_failure_is_user_friendly():
    container = FakeContainer(exit_code=128, logs=b"fatal: could not read Username: terminal prompts disabled")
    with pytest.raises(SandboxError, match="not found, or it is private"):
        with clone_repo("https://github.com/nobody/none", sandbox=make_sandbox(FakeClient(container))):
            pass


def test_clone_timeout_message_mentions_size():
    container = FakeContainer(finishes_after=10**6)
    with pytest.raises(SandboxError, match="too large"):
        with clone_repo("https://github.com/huge/repo", sandbox=make_sandbox(FakeClient(container), timeout=3)):
            pass


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://evil.com/a/b",
        "https://user:pw@github.com/a/b",
        "https://github.com:8443/a/b",
        "file:///etc/passwd",
        "ssh://git@github.com/a/b",
        "--upload-pack=touch /tmp/x",
        "https://github.com/a/b --evil",
        "",
    ],
)
def test_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_repo_url(url)


@pytest.mark.parametrize(
    "url", ["https://github.com/a/b", "https://github.com/a/b.git", "https://gitlab.com/g/p", "https://www.github.com/a/b"]
)
def test_accepts_public_urls(url):
    assert validate_repo_url(url) == url
