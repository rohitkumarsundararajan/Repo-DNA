from pathlib import Path

from repodna_worker.detect.language import detect_languages


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_counts_and_sorts_by_loc(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n\ny = 2\n")  # 2 LOC
    _write(tmp_path, "b.py", "z = 3\n")  # 1 LOC
    _write(tmp_path, "web/app.ts", "a\nb\nc\nd\n")  # 4 LOC

    stats = detect_languages(tmp_path)

    assert [s.name for s in stats] == ["TypeScript", "Python"]
    ts, py = stats
    assert (ts.files, ts.loc, ts.share) == (1, 4, 0.5714)
    assert (py.files, py.loc, py.share) == (2, 3, 0.4286)


def test_ignored_dirs_are_skipped(tmp_path):
    _write(tmp_path, "src/main.py", "print(1)\n")
    _write(tmp_path, "node_modules/x.js", "x\n")
    _write(tmp_path, ".git/hooks/y.py", "y\n")
    _write(tmp_path, "build/z.py", "z\n")
    _write(tmp_path, "dist/d.js", "d\n")
    _write(tmp_path, "vendor/v.go", "v\n")
    _write(tmp_path, "venv/lib.py", "l\n")

    stats = detect_languages(tmp_path)

    assert [s.name for s in stats] == ["Python"]
    assert stats[0].files == 1


def test_unknown_extensions_ignored_and_empty_repo(tmp_path):
    _write(tmp_path, "README.md", "hello\n")
    _write(tmp_path, "data.json", "{}\n")

    assert detect_languages(tmp_path) == []


def test_to_dict_shape(tmp_path):
    _write(tmp_path, "Main.java", "class Main {}\n")

    assert detect_languages(tmp_path)[0].to_dict() == {
        "name": "Java",
        "files": 1,
        "loc": 1,
        "share": 1.0,
    }