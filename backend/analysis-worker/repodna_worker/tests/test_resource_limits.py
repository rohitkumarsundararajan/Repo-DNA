import zipfile

import pytest

from repodna_worker.sandbox.resource_limits import (
    RepositoryLimitError,
    validate_repository,
)
from repodna_worker.sandbox.zip_extract import UnsafeZipError, extract_zip


def _write(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def test_repository_limits_count_files_and_total_size(tmp_path):
    _write(tmp_path, "src/a.py", b"1234")
    _write(tmp_path, "README.md", b"12")

    validate_repository(tmp_path, max_files=2, max_file_size=4, max_total_size=6)

    with pytest.raises(RepositoryLimitError, match="file count"):
        validate_repository(tmp_path, max_files=1, max_file_size=4, max_total_size=6)
    with pytest.raises(RepositoryLimitError, match="repository size"):
        validate_repository(tmp_path, max_files=2, max_file_size=4, max_total_size=5)


def test_repository_limit_rejects_oversized_individual_file(tmp_path):
    _write(tmp_path, "large.bin", b"12345")

    with pytest.raises(RepositoryLimitError, match="file exceeds size limit"):
        validate_repository(tmp_path, max_files=1, max_file_size=4, max_total_size=10)


def test_repository_limit_excludes_git_metadata(tmp_path):
    _write(tmp_path, ".git/objects/large.pack", b"x" * 100)
    _write(tmp_path, "src/app.py", b"x")

    validate_repository(tmp_path, max_files=1, max_file_size=1, max_total_size=1)


def test_zip_extractor_rejects_oversized_member_before_writing(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("large.py", b"12345")

    destination = tmp_path / "extracted"
    with pytest.raises(UnsafeZipError, match="member size limit"):
        extract_zip(archive, destination, max_file_size=4)

    assert not (destination / "large.py").exists()