from pathlib import Path

from repodna_worker.metrics.size import (
    compute_file_size,
    compute_repo_size,
    compute_size_from_parsed_files,
)
from repodna_worker.parsing.parser import parse_file


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


PY_SRC = """def simple(x):
    return x

class Foo:
    def method(self, x):
        return x
"""


def test_python_size_matches_parser_loc(tmp_path):
    path = _write(tmp_path, "mod.py", PY_SRC)
    parsed = parse_file(path, root=tmp_path)

    functions, classes = compute_file_size(path, root=tmp_path)

    assert [(f.function, f.loc) for f in functions] == [
        (f.name, f.loc) for f in parsed.functions
    ]
    assert [(c.class_name, c.loc) for c in classes] == [
        (c.name, c.loc) for c in parsed.classes
    ]
    assert functions[0].file == "mod.py"


def test_javascript_size(tmp_path):
    path = _write(
        tmp_path,
        "app.js",
        "function f(x) {\n  return x;\n}\n\nclass C {\n  m() {\n    return 1;\n  }\n}\n",
    )

    functions, classes = compute_file_size(path, root=tmp_path)

    assert [f.function for f in functions] == ["f", "m"]
    assert [c.class_name for c in classes] == ["C"]
    assert all(f.loc > 0 for f in functions)
    assert all(c.loc > 0 for c in classes)


def test_unsupported_and_missing_files_return_empty(tmp_path):
    path = _write(tmp_path, "notes.md", "# hi\n")
    assert compute_file_size(path) == ([], [])
    assert compute_file_size(tmp_path / "missing.py") == ([], [])


def test_to_dict_shapes(tmp_path):
    path = _write(tmp_path, "mod.py", "def f(x):\n    return x\n")

    functions, classes = compute_file_size(path, root=tmp_path)

    assert functions[0].to_dict() == {
        "file": "mod.py",
        "function": "f",
        "start_line": 1,
        "end_line": 2,
        "loc": 2,
    }
    assert classes == []


def test_compute_repo_size_sorted_and_flattened(tmp_path):
    _write(tmp_path, "b.py", "def g():\n    return 1\n")
    _write(tmp_path, "a.py", "def f():\n    return 1\n")

    functions, classes = compute_repo_size([tmp_path / "b.py", tmp_path / "a.py"], root=tmp_path)

    assert [(f.file, f.function) for f in functions] == [("a.py", "f"), ("b.py", "g")]
    assert classes == []


def test_compute_size_from_parsed_files_avoids_reparsing(tmp_path):
    path_a = _write(tmp_path, "a.py", "def f():\n    return 1\n")
    path_b = _write(tmp_path, "b.py", "class C:\n    def m(self):\n        return 1\n")

    parsed = [
        parse_file(path_a, root=tmp_path),
        parse_file(path_b, root=tmp_path),
    ]

    functions, classes = compute_size_from_parsed_files(parsed)

    assert [(f.file, f.function) for f in functions] == [("a.py", "f"), ("b.py", "m")]
    assert [(c.file, c.class_name) for c in classes] == [("b.py", "C")]