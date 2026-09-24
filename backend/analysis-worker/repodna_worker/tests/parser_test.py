from pathlib import Path

from repodna_worker.parsing.parser import MAX_FILE_BYTES, parse_file


def _write(root: Path, rel: str, text: str | bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


def _imports(parsed):
    return [(i.module, i.names, i.level) for i in parsed.imports]


def _calls(parsed):
    return {(c.name, c.caller) for c in parsed.calls}


PY_SRC = '''import os.path as osp, sys
from . import sibling
from ..pkg.mod import a as b, c
from lib import *

class Base:
    pass

class Child(Base, metaclass=Meta, Generic[T]):
    async def run(self):
        helper(1)
        self.svc.go()
        return other().chain()

def helper(x):
    return x
'''


def test_python(tmp_path):
    _write(tmp_path, "pkg/mod.py", PY_SRC)

    parsed = parse_file(tmp_path / "pkg/mod.py", root=tmp_path)

    assert parsed.path == "pkg/mod.py"
    assert parsed.language == "python"
    assert parsed.loc == 13
    assert _imports(parsed) == [
        ("os.path", [], 0),
        ("sys", [], 0),
        ("", ["sibling"], 1),
        ("pkg.mod", ["a", "c"], 2),
        ("lib", ["*"], 0),
    ]
    assert [i.is_relative for i in parsed.imports] == [False, False, True, True, False]
    assert [f.name for f in parsed.functions] == ["run", "helper"]
    assert [c.name for c in parsed.classes] == ["Base", "Child"]
    assert _calls(parsed) == {
        ("helper", "run"),
        ("self.svc.go", "run"),
        ("other", "run"),
        ("chain", "run"),
    }


def test_python_lines_and_loc(tmp_path):
    _write(tmp_path, "mod.py", PY_SRC)

    parsed = parse_file(tmp_path / "mod.py")

    assert [(f.name, f.start_line, f.end_line, f.loc) for f in parsed.functions] == [
        ("run", 10, 13, 4),
        ("helper", 15, 16, 2),
    ]
    assert [(c.name, c.start_line, c.end_line, c.loc) for c in parsed.classes] == [
        ("Base", 6, 7, 2),
        ("Child", 9, 13, 5),
    ]
    assert {(c.name, c.start_line) for c in parsed.calls} >= {("helper", 11), ("chain", 13)}


JS_SRC = """import React, { useState as us } from 'react';
import * as path from "path";
import './side-effect.css';
export * from './reexport';
export { a, b } from './names';
const fs = require('fs');
const lazy = () => import('./lazy');

function top() { helper(); obj.method(); new Widget(); }
const arrow = async () => { top(); };
class Comp extends React.Component {
  handle = () => { top(); };
  render() { return 1; }
}
"""


def test_javascript(tmp_path):
    _write(tmp_path, "src/app.js", JS_SRC)

    parsed = parse_file(tmp_path / "src/app.js", root=tmp_path)

    assert parsed.language == "javascript"
    assert _imports(parsed) == [
        ("react", ["default", "useState"], 0),
        ("path", ["*"], 0),
        ("./side-effect.css", [], 0),
        ("./reexport", ["*"], 0),
        ("./names", ["a", "b"], 0),
        ("fs", [], 0),
        ("./lazy", [], 0),
    ]
    assert [i.is_relative for i in parsed.imports] == [
        False, False, True, True, True, False, True,
    ]
    assert {f.name for f in parsed.functions} == {
        "lazy", "top", "arrow", "handle", "render",
    }
    assert [c.name for c in parsed.classes] == ["Comp"]
    calls = _calls(parsed)
    assert ("helper", "top") in calls
    assert ("obj.method", "top") in calls
    assert ("Widget", "top") in calls
    assert ("top", "arrow") in calls
    assert ("top", "handle") in calls
    # require() and import() are imports, not calls
    assert not any(c.name in ("require", "import") for c in parsed.calls)


TS_SRC = """import fs = require('fs');
import type { A } from './a';
abstract class X<T> extends Y<T> implements Z {
  public p = () => run();
  abstract q(): void;
}
function over(a: string): void;
function over(a: any): void { run(); }
"""


def test_typescript(tmp_path):
    _write(tmp_path, "a.ts", TS_SRC)

    parsed = parse_file(tmp_path / "a.ts")

    assert parsed.language == "typescript"
    assert _imports(parsed) == [("fs", [], 0), ("./a", ["A"], 0)]
    assert [c.name for c in parsed.classes] == ["X"]
    assert sorted(f.name for f in parsed.functions) == ["over", "p"]
    assert ("run", "over") in _calls(parsed)


def test_tsx(tmp_path):
    _write(
        tmp_path,
        "App.tsx",
        "import { x } from './x';\nexport const App = () => <div>{fmt(1)}</div>;\n",
    )

    parsed = parse_file(tmp_path / "App.tsx")

    assert parsed.language == "typescript"
    assert parsed.loc == 2
    assert _imports(parsed) == [("./x", ["x"], 0)]
    assert [f.name for f in parsed.functions] == ["App"]
    assert _calls(parsed) == {("fmt", "App")}


def test_syntax_errors_do_not_crash(tmp_path):
    _write(tmp_path, "bad.py", "def broken(:\n    pass\nimport os\n")
    _write(tmp_path, "bad.js", "function ( {\nconst x = require('y');\n")

    for name in ("bad.py", "bad.js"):
        parsed = parse_file(tmp_path / name)
        assert parsed is not None
        assert parsed.loc > 0


def test_skips(tmp_path):
    _write(tmp_path, "bin.py", b"\x00\x01\x02import os\n")
    _write(tmp_path, "huge.py", "#" * (MAX_FILE_BYTES + 1))
    _write(tmp_path, "notes.md", "# hi\n")

    assert parse_file(tmp_path / "bin.py") is None
    assert parse_file(tmp_path / "huge.py") is None
    assert parse_file(tmp_path / "notes.md") is None
    assert parse_file(tmp_path / "missing.py") is None


def test_file_at_size_limit_is_parsed(tmp_path):
    body = "x = 1\n"
    _write(tmp_path, "edge.py", body + "#" * (MAX_FILE_BYTES - len(body)))

    assert parse_file(tmp_path / "edge.py") is not None


def test_bom_and_non_utf8_are_tolerated(tmp_path):
    _write(tmp_path, "bom.py", b"\xef\xbb\xbfimport os\n")
    _write(tmp_path, "latin.py", b"# caf\xe9\nimport sys\n")

    assert _imports(parse_file(tmp_path / "bom.py")) == [("os", [], 0)]
    assert _imports(parse_file(tmp_path / "latin.py")) == [("sys", [], 0)]


def test_round_trips_through_to_dict(tmp_path):
    _write(tmp_path, "mod.py", PY_SRC)

    parsed = parse_file(tmp_path / "mod.py")

    assert type(parsed).from_dict(parsed.to_dict()) == parsed