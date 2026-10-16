import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from repodna_worker.parsing import parser as parser_module
from repodna_worker.parsing.runner import _chunk_paths, _parse_chunk, parse_repository


def _write(root: Path, rel: str, text: str = "x = 1\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# _chunk_paths
# --------------------------------------------------------------------------


def test_chunk_paths_empty():
    assert _chunk_paths([], 4) == []


def test_chunk_paths_covers_every_path_no_duplicates():
    paths = [f"f{i}.py" for i in range(37)]
    chunks = _chunk_paths(paths, workers=4)

    assert sum(len(c) for c in chunks) == len(paths)
    assert [p for chunk in chunks for p in chunk] == paths  # order preserved
    assert len(chunks) > 1  # actually split, not one giant chunk


def test_chunk_paths_never_more_chunks_than_paths():
    chunks = _chunk_paths(["a.py", "b.py"], workers=16)

    assert len(chunks) <= 2


# --------------------------------------------------------------------------
# parse_repository (real ProcessPoolExecutor, the default)
# --------------------------------------------------------------------------


def test_parses_across_processes_and_sorts_output(tmp_path):
    _write(tmp_path, "b/mod.py", "def g():\n    pass\n")
    _write(tmp_path, "a/mod.py", "def f():\n    pass\n")
    _write(tmp_path, "README.md", "not source\n")  # unsupported, discovered but skipped

    results = parse_repository(tmp_path, max_workers=2)

    assert [r.path for r in results] == ["a/mod.py", "b/mod.py"]
    assert [f.name for f in results[0].functions] == ["f"]


def test_empty_repository_returns_empty_list(tmp_path):
    assert parse_repository(tmp_path) == []


def test_explicit_paths_are_parsed_instead_of_walking(tmp_path):
    _write(tmp_path, "keep.py", "def kept():\n    pass\n")
    _write(tmp_path, "skip.py", "def skipped():\n    pass\n")

    results = parse_repository(tmp_path, paths=[tmp_path / "keep.py"], max_workers=1)

    assert [r.path for r in results] == ["keep.py"]


def test_missing_and_unsupported_explicit_paths_are_skipped_not_failed(
    tmp_path, caplog
):
    _write(tmp_path, "ok.py", "x = 1\n")

    with caplog.at_level(logging.WARNING):
        results = parse_repository(
            tmp_path,
            paths=[tmp_path / "ok.py", tmp_path / "missing.py", tmp_path / "ok.py"],
            max_workers=1,
        )

    assert [r.path for r in results] == ["ok.py", "ok.py"]
    assert not any("failed to parse" in r.message for r in caplog.records)


# --------------------------------------------------------------------------
# _parse_chunk: unit-level, in-process
# --------------------------------------------------------------------------


def test_parse_chunk_reports_success_and_skip(tmp_path):
    good = _write(tmp_path, "good.py", "x = 1\n")
    _write(tmp_path, "notes.md", "n/a\n")

    results = _parse_chunk([str(good), str(tmp_path / "notes.md")], str(tmp_path))

    (good_path, good_parsed, good_err), (md_path, md_parsed, md_err) = results
    assert good_parsed is not None and good_err is None
    assert md_parsed is None and md_err is None  # unsupported ext: a skip, not a failure


def test_parse_chunk_catches_unexpected_exception(tmp_path, monkeypatch):
    bad = _write(tmp_path, "bad.py", "x = 1\n")

    def boom(*_args, **_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(parser_module, "parse_file", boom)
    # runner imported parse_file by name, so patch it there too
    monkeypatch.setattr(
        "repodna_worker.parsing.runner.parse_file", boom, raising=True
    )

    [(path, parsed, error)] = _parse_chunk([str(bad)], str(tmp_path))

    assert parsed is None
    assert "kaboom" in error


# --------------------------------------------------------------------------
# Failure paths, exercised with ThreadPoolExecutor so monkeypatching applies
# --------------------------------------------------------------------------


def test_worker_exceptions_are_logged_and_excluded(tmp_path, monkeypatch, caplog):
    _write(tmp_path, "good.py", "x = 1\n")
    _write(tmp_path, "bad.py", "y = 2\n")

    real_parse_file = parser_module.parse_file

    def flaky(path, root=None):
        if str(path).endswith("bad.py"):
            raise RuntimeError("boom")
        return real_parse_file(path, root=root)

    monkeypatch.setattr("repodna_worker.parsing.runner.parse_file", flaky)

    with caplog.at_level(logging.WARNING):
        results = parse_repository(
            tmp_path, max_workers=2, executor_cls=ThreadPoolExecutor
        )

    assert [r.path for r in results] == ["good.py"]
    assert any(
        "failed to parse" in r.message and "bad.py" in r.message
        for r in caplog.records
    )


def test_lost_chunk_is_logged_and_others_still_returned(tmp_path, monkeypatch, caplog):
    _write(tmp_path, "a.py", "x = 1\n")
    _write(tmp_path, "b.py", "y = 2\n")

    # Force one chunk per file so we can make exactly one chunk's future fail.
    monkeypatch.setattr(
        "repodna_worker.parsing.runner._chunk_paths",
        lambda paths, workers: [[p] for p in paths],
    )

    real_parse_chunk = __import__(
        "repodna_worker.parsing.runner", fromlist=["_parse_chunk"]
    )._parse_chunk

    def flaky_chunk(chunk, root):
        if chunk and chunk[0].endswith("b.py"):
            raise RuntimeError("worker crashed")
        return real_parse_chunk(chunk, root)

    monkeypatch.setattr("repodna_worker.parsing.runner._parse_chunk", flaky_chunk)

    with caplog.at_level(logging.WARNING):
        results = parse_repository(
            tmp_path, max_workers=2, executor_cls=ThreadPoolExecutor
        )

    assert [r.path for r in results] == ["a.py"]
    assert any("worker failed" in r.message for r in caplog.records)


def test_large_repo_uses_multiple_chunks(tmp_path):
    for i in range(20):
        _write(tmp_path, f"m{i}.py", f"def f{i}():\n    pass\n")

    results = parse_repository(tmp_path, max_workers=4)

    assert len(results) == 20
    assert results == sorted(results, key=lambda r: r.path)