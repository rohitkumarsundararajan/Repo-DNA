"""Getting source onto disk: ZIP uploads (Git is covered in test_sandbox.py)."""

import zipfile

import pytest

from repodna_worker.consumer import config
from repodna_worker.sandbox.acquire import acquire_source
from repodna_worker.sandbox.zip_extract import UnsafeZipError


@pytest.fixture
def folders(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(config, "ZIP_ROOT", str(uploads))
    monkeypatch.setattr(config, "WORK_DIR", str(work))
    return uploads, work


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_zip_with_single_top_folder_is_flattened(folders):
    uploads, work = folders
    make_zip(uploads / "job.zip", {"proj-main/app.py": "x = 1\n", "proj-main/lib/util.py": "y = 2\n"})
    job = {"job_id": "j", "source_type": "zip", "zip_path": str(uploads / "job.zip"), "repo_url": None}
    with acquire_source(job) as path:
        assert (path / "app.py").is_file()
        assert (path / "lib" / "util.py").is_file()
    assert list(work.iterdir()) == []  # scratch space is cleaned up


def test_zip_with_files_at_top_level_is_kept_as_is(folders):
    uploads, _ = folders
    make_zip(uploads / "job.zip", {"app.py": "x = 1\n", "other.py": "y = 2\n"})
    job = {"job_id": "j", "source_type": "zip", "zip_path": str(uploads / "job.zip"), "repo_url": None}
    with acquire_source(job) as path:
        assert sorted(p.name for p in path.iterdir()) == ["app.py", "other.py"]


def test_zip_outside_uploads_folder_is_refused(folders, tmp_path):
    make_zip(tmp_path / "elsewhere.zip", {"a.py": "1\n"})
    job = {"job_id": "j", "source_type": "zip", "zip_path": str(tmp_path / "elsewhere.zip"), "repo_url": None}
    with pytest.raises(UnsafeZipError):
        with acquire_source(job):
            pass


def test_zip_path_traversal_is_refused(folders):
    uploads, _ = folders
    make_zip(uploads / "ok.zip", {"a.py": "1\n"})
    job = {"job_id": "j", "source_type": "zip", "zip_path": str(uploads / ".." / "etc" / "x.zip"), "repo_url": None}
    with pytest.raises(UnsafeZipError):
        with acquire_source(job):
            pass


def test_missing_zip_is_a_clear_error(folders):
    uploads, _ = folders
    job = {"job_id": "j", "source_type": "zip", "zip_path": str(uploads / "gone.zip"), "repo_url": None}
    with pytest.raises(FileNotFoundError):
        with acquire_source(job):
            pass


def test_zip_slip_member_is_refused(folders):
    uploads, _ = folders
    make_zip(uploads / "evil.zip", {"../../evil.py": "1\n"})
    job = {"job_id": "j", "source_type": "zip", "zip_path": str(uploads / "evil.zip"), "repo_url": None}
    with pytest.raises(UnsafeZipError):
        with acquire_source(job):
            pass


def test_unknown_source_type():
    with pytest.raises(ValueError):
        with acquire_source({"source_type": "ftp"}):
            pass
