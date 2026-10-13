"""Safe extraction of tar streams coming out of the sandbox."""

import io
import tarfile

import pytest

from repodna_worker.sandbox.archive import UnsafeArchiveError, extract_tar_stream
from repodna_worker.sandbox.resource_limits import RepositoryLimitError

BIG = 10**9


def make_tar(entries):
    """entries: list of (name, bytes | None for dir | ("symlink", target))."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, content in entries:
            info = tarfile.TarInfo(name)
            if content is None:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            elif isinstance(content, tuple):
                info.type = tarfile.SYMTYPE
                info.linkname = content[1]
                tar.addfile(info)
            else:
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
    data = buffer.getvalue()
    # Deliver in small chunks, like docker's get_archive.
    return [data[i : i + 700] for i in range(0, len(data), 700)]


def extract(entries, tmp_path, **kwargs):
    options = {"max_files": 100, "max_total_size": BIG}
    options.update(kwargs)
    return extract_tar_stream(make_tar(entries), tmp_path / "out", **options)


def test_extracts_files_and_strips_top_folder(tmp_path):
    result = extract(
        [("repository", None), ("repository/a.py", b"print(1)\n"), ("repository/pkg", None),
         ("repository/pkg/b.py", b"x = 2\n")],
        tmp_path,
    )
    assert result.files == 2
    assert (tmp_path / "out" / "a.py").read_bytes() == b"print(1)\n"
    assert (tmp_path / "out" / "pkg" / "b.py").read_bytes() == b"x = 2\n"


def test_large_file_across_many_chunks_is_intact(tmp_path):
    payload = bytes(range(256)) * 5000
    extract([("repository/big.bin", payload)], tmp_path)
    assert (tmp_path / "out" / "big.bin").read_bytes() == payload


@pytest.mark.parametrize("name", ["repository/../evil.py", "/etc/passwd", "../evil.py"])
def test_rejects_path_traversal(tmp_path, name):
    with pytest.raises(UnsafeArchiveError):
        extract([(name, b"x")], tmp_path)
    assert not (tmp_path / "evil.py").exists()


def test_symlinks_are_skipped_not_followed(tmp_path):
    result = extract(
        [("repository/ok.py", b"1\n"), ("repository/link", ("symlink", "/etc/passwd"))],
        tmp_path,
    )
    assert result.files == 1 and result.skipped == 1
    assert not (tmp_path / "out" / "link").exists()


def test_git_folder_is_ignored(tmp_path):
    result = extract(
        [("repository/.git", None), ("repository/.git/config", b"secret"), ("repository/a.py", b"1\n")],
        tmp_path,
    )
    assert result.files == 1
    assert not (tmp_path / "out" / ".git").exists()


def test_file_count_limit(tmp_path):
    with pytest.raises(RepositoryLimitError, match="file count"):
        extract([(f"repository/f{i}.py", b"1") for i in range(5)], tmp_path, max_files=3)


def test_total_size_limit(tmp_path):
    with pytest.raises(RepositoryLimitError, match="size"):
        extract([("repository/a.bin", b"x" * 600), ("repository/b.bin", b"x" * 600)], tmp_path,
                max_total_size=1000)
