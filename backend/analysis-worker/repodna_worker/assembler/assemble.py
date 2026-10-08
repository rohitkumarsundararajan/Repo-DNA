from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema


SCHEMA_PATH = (
    Path(__file__).resolve()
    .parents[4]
    / "contract"
    / "result.schema.json"
)


def _load_schema() -> dict[str, Any]:
    """Load the repository result JSON schema."""
    try:
        with SCHEMA_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise ValueError(
            f"Result schema not found: {SCHEMA_PATH}"
        ) from exc


def _validate_result(result: dict[str, Any]) -> None:
    """
    Validate the final result against contract/result.schema.json.

    Raises:
        ValueError: If validation fails, including the failing field.
    """
    schema = _load_schema()

    try:
        jsonschema.validate(
            instance=result,
            schema=schema,
        )
    except jsonschema.ValidationError as exc:
        path = list(exc.absolute_path)

        if path:
            field = ".".join(str(item) for item in path)
        else:
            field = "<root>"

        raise ValueError(
            f"Result validation failed at field "
            f"'{field}': {exc.message}"
        ) from exc


def assemble_result(
    *,
    schema_version: str,
    job_id: str,
    repo_meta: dict[str, Any],
    languages: list[dict[str, Any]],
    frameworks: list[dict[str, Any]],
    files: list[dict[str, Any]],
    hotspots: list[dict[str, Any]],
    graph: dict[str, Any],
    cycles: list[list[str]],
    architecture: dict[str, Any],
    scores: dict[str, Any],
) -> dict[str, Any]:
    """
    Assemble and validate the final Repo-DNA analysis result.

    The returned structure follows contract/result.schema.json.
    """

    result = {
        "schema_version": schema_version,
        "job_id": job_id,
        "repo_meta": repo_meta,
        "languages": languages,
        "frameworks": frameworks,
        "files": files,
        "hotspots": hotspots,
        "graph": graph,
        "cycles": cycles,
        "architecture": architecture,
        "scores": {
            "architecture_dna": scores["architecture_dna"],
            "code_dna": scores["code_dna"],
            "quality_dna": scores["quality_dna"],
        },
    }

    _validate_result(result)

    return result


def assemble(
    *,
    schema_version: str,
    job_id: str,
    repo_meta: dict[str, Any],
    languages: list[dict[str, Any]],
    frameworks: list[dict[str, Any]],
    files: list[dict[str, Any]],
    hotspots: list[dict[str, Any]],
    graph: dict[str, Any],
    cycles: list[list[str]],
    architecture: dict[str, Any],
    scores: dict[str, Any],
) -> dict[str, Any]:
    """Public alias for assemble_result."""
    return assemble_result(
        schema_version=schema_version,
        job_id=job_id,
        repo_meta=repo_meta,
        languages=languages,
        frameworks=frameworks,
        files=files,
        hotspots=hotspots,
        graph=graph,
        cycles=cycles,
        architecture=architecture,
        scores=scores,
    )