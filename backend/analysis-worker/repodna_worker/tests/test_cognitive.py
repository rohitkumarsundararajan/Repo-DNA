from pathlib import Path

from repodna_worker.metrics.cognitive import (
    MAX_FILE_BYTES,
    compute_file_cognitive_complexity,
    compute_repo_cognitive_complexity,
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

class Foo:
    def method(self, x):
        if x:
            return 1
        return 0
"""


def test_python_matches_cognitive_complexity_library(tmp_path):
    # Values pinned directly against cognitive_complexity.api.get_cognitive_complexity
    # for this exact source, run independently of this module.
    path = _write(tmp_path, "mod.py", PY_SRC)

    by_name = _by_name(compute_file_cognitive_complexity(path, root=tmp_path))

    assert by_name["simple"].complexity == 0
    assert by_name["branchy"].complexity == 6
    assert by_name["Foo.method"].complexity == 1
    assert by_name["branchy"].file == "mod.py"
    assert (by_name["branchy"].start_line, by_name["branchy"].end_line) == (4, 14)


def test_python_excludes_nested_closures_as_separate_entries(tmp_path):
    path = _write(
        tmp_path,
        "mod.py",
        "def outer(x):\n"
        "    def inner(y):\n"
        "        if y:\n            return 1\n        return 0\n"
        "    if x:\n        return inner(x)\n    return 0\n",
    )

    results = compute_file_cognitive_complexity(path)

    assert [r.function for r in results] == ["outer"]
    assert results[0].complexity > 0  # inner's branch still counts toward outer


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

class Foo {
  method(x) {
    if (x) {
      return 1;
    }
    return 0;
  }
}
"""


def test_javascript_branch_and_nesting_rule(tmp_path):
    # Hand count for `branchy`: outer-if(1) + inner-if(2) + elif-if(2)
    # + for(1) + inner if-in-for(2) = 8
    path = _write(tmp_path, "app.js", JS_SRC)

    by_name = _by_name(compute_file_cognitive_complexity(path, root=tmp_path))

    assert by_name["simple"].complexity == 0
    assert by_name["branchy"].complexity == 8
    assert by_name["method"].complexity == 1
    assert by_name["branchy"].file == "app.js"


def test_typescript_and_tsx(tmp_path):
    ts_path = _write(tmp_path, "a.ts", JS_SRC.replace("function simple(x) {", "function simple(x: number) {"))
    tsx_path = _write(
        tmp_path,
        "App.tsx",
        "export function App(x: number) {\n  if (x) {\n    return <div>yes</div>;\n  }\n  return <div>no</div>;\n}\n",
    )

    ts_by_name = _by_name(compute_file_cognitive_complexity(ts_path))
    assert ts_by_name["branchy"].complexity == 8

    [tsx_result] = compute_file_cognitive_complexity(tsx_path)
    assert tsx_result.function == "App"
    assert tsx_result.complexity == 1


def test_unsupported_extension_returns_empty(tmp_path):
    path = _write(tmp_path, "notes.md", "# hi\n")
    assert compute_file_cognitive_complexity(path) == []


def test_python_syntax_error_does_not_crash(tmp_path):
    path = _write(tmp_path, "bad.py", "def broken(:\n    pass\n")
    assert compute_file_cognitive_complexity(path) == []


def test_missing_and_oversized_files_skipped(tmp_path):
    assert compute_file_cognitive_complexity(tmp_path / "missing.py") == []

    path = _write(tmp_path, "huge.py", "x = 1\n" + "#" * (MAX_FILE_BYTES + 1))
    assert compute_file_cognitive_complexity(path) == []


def test_to_dict_shape(tmp_path):
    path = _write(tmp_path, "mod.py", "def f(x):\n    return x\n")

    assert compute_file_cognitive_complexity(path)[0].to_dict() == {
        "file": path.as_posix(),
        "function": "f",
        "complexity": 0,
        "start_line": 1,
        "end_line": 2,
    }


def test_compute_repo_cognitive_complexity_sorted_and_flattened(tmp_path):
    _write(tmp_path, "b.py", "def g():\n    return 1\n")
    _write(tmp_path, "a.py", "def f():\n    if True:\n        pass\n")

    results = compute_repo_cognitive_complexity(
        [tmp_path / "b.py", tmp_path / "a.py"], root=tmp_path
    )

    assert [(r.file, r.function) for r in results] == [("a.py", "f"), ("b.py", "g")]