from pathlib import Path
from unittest.mock import patch

from repodna_worker.graph.madge import MadgeError, MadgeRunner


def test_run_json_parses_madge_output(tmp_path: Path) -> None:
    """Test parsing Madge JSON output."""

    runner = MadgeRunner(tmp_path)

    fake_result = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": (
                '{"src/app.js": ["src/utils/helper.js"], '
                '"src/utils/helper.js": []}'
            ),
            "stderr": "",
        },
    )()

    with patch(
        "repodna_worker.graph.madge.subprocess.run",
        return_value=fake_result,
    ) as mock_run:
        result = runner.run_json()

    assert result == {
        "src/app.js": ["src/utils/helper.js"],
        "src/utils/helper.js": [],
    }

    mock_run.assert_called_once()


def test_run_json_raises_when_madge_fails(tmp_path: Path) -> None:
    """Test that Madge failures raise MadgeError."""

    runner = MadgeRunner(tmp_path)

    fake_result = type(
        "Result",
        (),
        {
            "returncode": 1,
            "stdout": "",
            "stderr": "Madge command failed",
        },
    )()

    with patch(
        "repodna_worker.graph.madge.subprocess.run",
        return_value=fake_result,
    ):
        try:
            runner.run_json()
            assert False, "MadgeError was not raised"
        except MadgeError as exc:
            assert "Madge command failed" in str(exc)


def test_run_json_rejects_invalid_json(tmp_path: Path) -> None:
    """Test that invalid Madge JSON raises MadgeError."""

    runner = MadgeRunner(tmp_path)

    fake_result = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": "not valid json",
            "stderr": "",
        },
    )()

    with patch(
        "repodna_worker.graph.madge.subprocess.run",
        return_value=fake_result,
    ):
        try:
            runner.run_json()
            assert False, "MadgeError was not raised"
        except MadgeError as exc:
            assert "invalid JSON" in str(exc)


def test_run_circular_parses_cycles(tmp_path: Path) -> None:
    """Test parsing Madge circular dependency output."""

    runner = MadgeRunner(tmp_path)

    fake_result = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": (
                "src/a.js -> src/b.js -> src/a.js\n"
                "src/c.js -> src/d.js -> src/c.js\n"
            ),
            "stderr": "",
        },
    )()

    with patch(
        "repodna_worker.graph.madge.subprocess.run",
        return_value=fake_result,
    ):
        result = runner.run_circular()

    assert result == [
        [
            "src/a.js",
            "src/b.js",
            "src/a.js",
        ],
        [
            "src/c.js",
            "src/d.js",
            "src/c.js",
        ],
    ]


def test_build_graph_creates_nodes_and_edges(tmp_path: Path) -> None:
    """Test converting Madge output into graph nodes and edges."""

    runner = MadgeRunner(tmp_path)

    json_result = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": (
                '{"src/app.js": ["src/utils/helper.js"], '
                '"src/utils/helper.js": []}'
            ),
            "stderr": "",
        },
    )()

    circular_result = type(
        "Result",
        (),
        {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        },
    )()

    with patch(
        "repodna_worker.graph.madge.subprocess.run",
        side_effect=[
            json_result,
            circular_result,
        ],
    ):
        result = runner.build_graph()

    assert result["nodes"] == [
        "src/app.js",
        "src/utils/helper.js",
    ]

    assert result["edges"] == [
        {
            "source": "src/app.js",
            "target": "src/utils/helper.js",
        }
    ]

    assert result["cycles"] == []