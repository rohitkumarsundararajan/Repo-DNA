import pytest

from repodna_worker.assembler.assemble import assemble_result


def valid_input():
    return {
        "schema_version": "1.0.0",
        "job_id": "123e4567-e89b-12d3-a456-426614174000",
        "repo_meta": {
            "repo_url": "https://github.com/example/repo",
            "source_type": "git",
            "total_files": 1,
            "total_loc": 10,
        },
        "languages": [
            {
                "name": "Python",
                "file_count": 1,
                "loc": 10,
                "percentage": 100.0,
            }
        ],
        "frameworks": [],
        "files": [
            {
                "path": "controllers/UserController.py",
                "loc": 10,
                "cyclomatic": 2,
                "cognitive": 1,
                "max_nesting": 1,
            }
        ],
        "hotspots": [],
        "graph": {
            "nodes": [
                {
                    "path": "controllers/UserController.py",
                    "language": "Python",
                    "folder": "controllers",
                    "fan_in": 0,
                    "fan_out": 0,
                }
            ],
            "edges": [],
        },
        "cycles": [],
        "architecture": {
            "pattern": "layered",
            "evidence": [],
            "violations": [],
        },
        "scores": {
            "architecture_dna": 100.0,
            "code_dna": 100.0,
            "quality_dna": 100.0,
        },
    }


def test_assemble_valid_result():
    data = valid_input()

    result = assemble_result(**data)

    assert result["schema_version"] == "1.0.0"
    assert result["job_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert result["scores"]["architecture_dna"] == 100.0


def test_assemble_preserves_sections():
    data = valid_input()

    result = assemble_result(**data)

    assert result["repo_meta"] == data["repo_meta"]
    assert result["languages"] == data["languages"]
    assert result["frameworks"] == data["frameworks"]
    assert result["files"] == data["files"]
    assert result["hotspots"] == data["hotspots"]
    assert result["graph"] == data["graph"]
    assert result["cycles"] == data["cycles"]
    assert result["architecture"] == data["architecture"]


def test_invalid_score_fails_validation():
    data = valid_input()

    data["scores"]["architecture_dna"] = 150

    with pytest.raises(
        ValueError,
        match="architecture_dna",
    ):
        assemble_result(**data)


def test_invalid_architecture_pattern_fails_validation():
    data = valid_input()

    data["architecture"]["pattern"] = "invalid"

    with pytest.raises(
        ValueError,
        match="pattern",
    ):
        assemble_result(**data)


def test_invalid_file_field_fails_validation():
    data = valid_input()

    data["files"][0]["loc"] = -1

    with pytest.raises(
        ValueError,
        match="loc",
    ):
        assemble_result(**data)