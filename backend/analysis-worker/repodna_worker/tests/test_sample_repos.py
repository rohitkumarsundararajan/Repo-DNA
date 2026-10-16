from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from repodna_worker.detect.frameworks import detect_frameworks
from repodna_worker.detect.language import detect_languages
from repodna_worker.metrics.aggregate import build_metrics
from repodna_worker.metrics.cyclomatic import compute_file_complexity
from repodna_worker.parsing.runner import parse_repository


SAMPLE_REPOS = Path(__file__).parent / "fixtures" / "sample_repos"


@pytest.mark.parametrize(
    ("repo_name", "language", "framework", "ecosystem"),
    [
        ("python_app", "Python", "Flask", "python"),
        ("javascript_app", "JavaScript", "React", "javascript"),
    ],
)
def test_sample_repo_detection(repo_name, language, framework, ecosystem):
    root = SAMPLE_REPOS / repo_name

    languages = detect_languages(root)
    frameworks = detect_frameworks(root)

    assert [item.name for item in languages] == [language]
    assert [(item.name, item.ecosystem) for item in frameworks] == [
        (framework, ecosystem)
    ]


@pytest.mark.parametrize(
    ("repo_name", "source_path", "language", "functions", "imports"),
    [
        (
            "python_app",
            "app.py",
            "python",
            ["normalize_name", "classify_score"],
            [("flask", ["Flask"])],
        ),
        (
            "javascript_app",
            "src/app.js",
            "javascript",
            ["normalizeName", "classifyScore"],
            [("react", ["default"])],
        ),
    ],
)
def test_sample_repo_parser_output(
    repo_name, source_path, language, functions, imports
):
    root = SAMPLE_REPOS / repo_name

    [parsed] = parse_repository(
        root, max_workers=1, executor_cls=ThreadPoolExecutor
    )

    assert parsed.path == source_path
    assert parsed.language == language
    assert [function.name for function in parsed.functions] == functions
    assert [(item.module, item.names) for item in parsed.imports] == imports


@pytest.mark.parametrize(
    ("repo_name", "source_path", "expected_metrics"),
    [
        (
            "python_app",
            "app.py",
            {
                "path": "app.py",
                "loc": 8,
                "cyclomatic": 3,
                "cognitive": 1,
                "max_nesting": 1,
            },
        ),
        (
            "javascript_app",
            "src/app.js",
            {
                "path": "src/app.js",
                "loc": 10,
                "cyclomatic": 3,
                "cognitive": 1,
                "max_nesting": 1,
            },
        ),
    ],
)
def test_sample_repo_metrics_and_hand_checked_radon_values(
    repo_name, source_path, expected_metrics
):
    root = SAMPLE_REPOS / repo_name
    parsed = parse_repository(root, max_workers=1, executor_cls=ThreadPoolExecutor)

    files, hotspots = build_metrics(parsed, root=root)

    assert files == [expected_metrics]
    # Hand count for each Python function: normalize_name has only the base
    # path (1); classify_score has one if branch plus the base path (2).
    if repo_name == "python_app":
        complexities = {
            item.function: item.complexity
            for item in compute_file_complexity(root / source_path, root=root)
        }
        assert complexities == {
            "normalize_name": 1,
            "classify_score": 2,
        }
    assert hotspots == [
        {"path": source_path, "metric": "cyclomatic", "value": 2},
        {"path": source_path, "metric": "cyclomatic", "value": 1},
    ]
