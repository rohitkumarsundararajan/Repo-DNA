from pathlib import Path

from repodna_worker.metrics.cyclomatic import (
    MAX_FILE_BYTES,
    compute_file_complexity,
    compute_repo_complexity,
)


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _by_name(results):
    return {r.function: r for r in results}


PY_SRC = '''def simple(x):
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
'''


def test_python_complexity_hand_checked(tmp_path):
    # Hand count for `branchy`: 1 (base) + if + nested if + elif + for + if = 6
    path = _write(tmp_path, "mod.py", PY_SRC)

    results = compute_file_complexity(path, root=tmp_path)
    by_name = _by_name(results)

    assert by_name["simple"].complexity == 1
    assert by_name["branchy"].complexity == 6
    assert by_name["Foo.method"].complexity == 2
    assert by_name["branchy"].file == "mod.py"
    assert (by_name["branchy"].start_line, by_name["branchy"].end_line) == (4, 14)
    assert "Foo" not in by_name  # the Class aggregate block itself is excluded


def test_python_flagging_threshold(tmp_path):
    # 14 independent `if` branches -> complexity 15 (1 base + 14), right at
    # the spec threshold.
    body = "\n".join(f"    if x == {i}:\n        pass" for i in range(14))
    src = f"def many_branches(x):\n{body}\n    return x\n"
    path = _write(tmp_path, "many.py", src)

    [result] = compute_file_complexity(path)

    assert result.complexity == 15
    assert result.is_flagged is True


def test_python_below_threshold_not_flagged(tmp_path):
    path = _write(tmp_path, "mod.py", PY_SRC)

    [result] = [r for r in compute_file_complexity(path) if r.function == "branchy"]

    assert result.complexity < 15
    assert result.is_flagged is False


JS_SRC = """function simple(x) {
  return x;
}

function branchy(x) {
  if (x > 0) {
    if (x > 10) {
      return 1;
    }
    return 2;
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

const arrow = (x) => {
  if (x) return 1;
  return 0;
};
"""


def test_javascript_complexity(tmp_path):
    path = _write(tmp_path, "app.js", JS_SRC)

    by_name = _by_name(compute_file_complexity(path, root=tmp_path))

    assert by_name["simple"].complexity == 1
    assert by_name["branchy"].complexity == 6
    assert by_name["method"].complexity == 2
    assert by_name["arrow"].complexity == 2
    assert by_name["branchy"].file == "app.js"


def test_typescript_complexity(tmp_path):
    ts_src = JS_SRC.replace(
        "function simple(x) {", "function simple(x: number): number {"
    )
    path = _write(tmp_path, "app.ts", ts_src)

    by_name = _by_name(compute_file_complexity(path))

    assert by_name["branchy"].complexity == 6


def test_tsx_complexity(tmp_path):
    path = _write(
        tmp_path,
        "App.tsx",
        "export function App(x: number) {\n"
        "  if (x) {\n    return <div>yes</div>;\n  }\n  return <div>no</div>;\n}\n",
    )

    [result] = compute_file_complexity(path)

    assert result.function == "App"
    assert result.complexity == 2


def test_unsupported_extension_returns_empty(tmp_path):
    path = _write(tmp_path, "notes.md", "# hi\n")

    assert compute_file_complexity(path) == []


def test_python_syntax_error_does_not_crash(tmp_path):
    path = _write(tmp_path, "bad.py", "def broken(:\n    pass\n")

    assert compute_file_complexity(path) == []


def test_missing_file_returns_empty(tmp_path):
    assert compute_file_complexity(tmp_path / "missing.py") == []
    assert compute_file_complexity(tmp_path / "missing.js") == []


def test_oversized_file_skipped(tmp_path):
    path = _write(tmp_path, "huge.py", "x = 1\n" + "#" * (MAX_FILE_BYTES + 1))

    assert compute_file_complexity(path) == []


def test_to_dict_shape(tmp_path):
    path = _write(tmp_path, "mod.py", "def f(x):\n    return x\n")

    assert compute_file_complexity(path)[0].to_dict() == {
        "file": path.as_posix(),
        "function": "f",
        "complexity": 1,
        "start_line": 1,
        "end_line": 2,
        "is_flagged": False,
    }


def test_compute_repo_complexity_sorted_and_flattened(tmp_path):
    _write(tmp_path, "b.py", "def g():\n    return 1\n")
    _write(tmp_path, "a.py", "def f():\n    if True:\n        pass\n")
    _write(tmp_path, "skip.md", "n/a\n")

    results = compute_repo_complexity(
        [tmp_path / "b.py", tmp_path / "a.py", tmp_path / "skip.md"], root=tmp_path
    )

    assert [(r.file, r.function) for r in results] == [("a.py", "f"), ("b.py", "g")]


def test_compute_repo_complexity_one_bad_file_does_not_stop_others(tmp_path):
    _write(tmp_path, "good.py", "def ok():\n    return 1\n")
    _write(tmp_path, "bad.py", "def broken(:\n")

    results = compute_repo_complexity([tmp_path / "bad.py", tmp_path / "good.py"])

    assert [r.function for r in results] == ["ok"]