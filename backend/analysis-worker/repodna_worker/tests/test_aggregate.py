import json
from pathlib import Path

import jsonschema

from repodna_worker.metrics.aggregate import build_metrics
from repodna_worker.parsing.parser import parse_file


def _write(root: Path, relative_path: str, source: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_build_metrics_and_validate_contract_shape(tmp_path):
    source_path = _write(
        tmp_path,
        "src/app.py",
        "def plain(value):\n"
        "    return value\n"
        "\n"
        "def branchy(value):\n"
        "    if value:\n"
        "        if value > 1:\n"
        "            return 1\n"
        "    return 0\n",
    )
    parsed = parse_file(source_path, root=tmp_path)

    files, hotspots = build_metrics([parsed], root=tmp_path, top_n=1)

    assert files == [
        {
            "path": "src/app.py",
            "loc": 7,
            "cyclomatic": 4,
            "cognitive": 3,
            "max_nesting": 2,
        }
    ]
    assert hotspots == [
        {"path": "src/app.py", "metric": "cyclomatic", "value": 3}
    ]

    schema_path = (
        Path(__file__).resolve().parents[4] / "contract" / "result.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(files, schema["properties"]["files"])
    jsonschema.validate(hotspots, schema["properties"]["hotspots"])


def test_build_metrics_supports_javascript_nesting(tmp_path):
    source_path = _write(
        tmp_path,
        "src/app.js",
        "function nested(value) {\n"
        "  if (value) {\n"
        "    while (value) {\n"
        "      return value;\n"
        "    }\n"
        "  }\n"
        "  return 0;\n"
        "}\n",
    )
    parsed = parse_file(source_path, root=tmp_path)

    files, hotspots = build_metrics([parsed], root=tmp_path)

    assert files[0]["max_nesting"] == 2
    assert files[0]["cyclomatic"] == 3
    assert files[0]["cognitive"] == 3
    assert hotspots[0]["path"] == "src/app.js"


def test_build_metrics_empty_and_top_n_validation(tmp_path):
    assert build_metrics([], root=tmp_path) == ([], [])

    try:
        build_metrics([], root=tmp_path, top_n=-1)
    except ValueError as error:
        assert str(error) == "top_n must be non-negative"
    else:
        raise AssertionError("negative top_n should fail")