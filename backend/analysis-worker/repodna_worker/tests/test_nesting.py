from pathlib import Path

from repodna_worker.metrics.nesting import (
    MAX_FILE_BYTES,
    compute_file_nesting,
    compute_repo_nesting,
)


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _by_name(results):
    return {r.function: r for r in results}


PY_SRC = """def simple(x):
    return x

def branchy(x):
    if x > 0:
        if x > 10:
            return 1
        return 2
    elif x < 0:
        return -1
    for i in range(x):
        if i % 2:
            continue
    return 0

def deeply_nested(x):
    if x:
        for i in range(x):
            if i:
                while i:
                    i -= 1
    return 0

class Foo:
    def method(self, x):
        if x:
            return 1
        return 0
"""


def test_python_max_nesting(tmp_path):
    path = _write(tmp_path, "mod.py", PY_SRC)

    by_name = _by_name(compute_file_nesting(path, root=tmp_path))

    assert by_name["simple"].max_nesting == 0
    assert by_name["branchy"].max_nesting == 2
    assert by_name["deeply_nested"].max_nesting == 4
    assert by_name["Foo.method"].max_nesting == 1
    assert by_name["branchy"].file == "mod.py"


def test_python_excludes_nested_closures_as_separate_entries(tmp_path):
    path = _write(
        tmp_path,
        "mod.py",
        "def outer(x):\n"
        "    def inner(y):\n"
        "        if y:\n            return 1\n        return 0\n"
        "    return 0\n",
    )

    results = compute_file_nesting(path)

    assert [r.function for r in results] == ["outer"]
    assert results[0].max_nesting == 0  # inner's nesting doesn't bleed into outer


JS_SRC = """function simple(x) {
  return x;
}

function branchy(x) {
  if (x > 0) {
    if (x > 10) {
      return 1;
    }
  } else if (x < 0) {
    return -1;
  }
  for (let i = 0; i < x; i++) {
    if (i % 2) continue;
  }
  return 0;
}

function deeplyNested(x) {
  if (x) {
    for (let i = 0; i < x; i++) {
      if (i) {
        while (i) { i--; }
      }
    }
  }
  return 0;
}
"""


def test_javascript_max_nesting(tmp_path):
    path = _write(tmp_path, "app.js", JS_SRC)

    by_name = _by_name(compute_file_nesting(path, root=tmp_path))

    assert by_name["simple"].max_nesting == 0
    assert by_name["branchy"].max_nesting == 2
    assert by_name["deeplyNested"].max_nesting == 4
    assert by_name["branchy"].file == "app.js"


def test_typescript_and_tsx(tmp_path):
    ts_path = _write(tmp_path, "a.ts", JS_SRC.replace("function simple(x) {", "function simple(x: number) {"))
    tsx_path = _write(
        tmp_path,
        "App.tsx",
        "export function App(x: number) {\n  if (x) {\n    if (x > 1) {\n      return <div>yes</div>;\n    }\n  }\n  return <div>no</div>;\n}\n",
    )

    ts_by_name = _by_name(compute_file_nesting(ts_path))
    assert ts_by_name["branchy"].max_nesting == 2

    [tsx_result] = compute_file_nesting(tsx_path)
    assert tsx_result.max_nesting == 2


def test_unsupported_extension_returns_empty(tmp_path):
    path = _write(tmp_path, "notes.md", "# hi\n")
    assert compute_file_nesting(path) == []


def test_python_syntax_error_does_not_crash(tmp_path):
    path = _write(tmp_path, "bad.py", "def broken(:\n    pass\n")
    assert compute_file_nesting(path) == []


def test_missing_and_oversized_files_skipped(tmp_path):
    assert compute_file_nesting(tmp_path / "missing.py") == []

    path = _write(tmp_path, "huge.py", "x = 1\n" + "#" * (MAX_FILE_BYTES + 1))
    assert compute_file_nesting(path) == []


def test_to_dict_shape(tmp_path):
    path = _write(tmp_path, "mod.py", "def f(x):\n    if x:\n        return 1\n    return 0\n")

    assert compute_file_nesting(path)[0].to_dict() == {
        "file": path.as_posix(),
        "function": "f",
        "max_nesting": 1,
        "start_line": 1,
        "end_line": 4,
    }


def test_compute_repo_nesting_sorted_and_flattened(tmp_path):
    _write(tmp_path, "b.py", "def g():\n    return 1\n")
    _write(tmp_path, "a.py", "def f():\n    if True:\n        pass\n")

    results = compute_repo_nesting([tmp_path / "b.py", tmp_path / "a.py"], root=tmp_path)

    assert [(r.file, r.function) for r in results] == [("a.py", "f"), ("b.py", "g")]