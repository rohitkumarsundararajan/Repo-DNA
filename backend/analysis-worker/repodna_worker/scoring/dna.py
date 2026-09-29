from __future__ import annotations

from typing import Any


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Clamp a numeric score to the inclusive 0-100 range."""
    return max(minimum, min(maximum, value))


def _round_score(value: float) -> float:
    """Return a stable score rounded to two decimal places."""
    return round(_clamp(value), 2)


def _get_violations(architecture: Any) -> list[dict[str, Any]]:
    """Extract architecture violations from supported result shapes."""
    if not isinstance(architecture, dict):
        return []

    violations = architecture.get("violations", [])

    if isinstance(violations, list):
        return [
            item for item in violations
            if isinstance(item, dict)
        ]

    return []


def _get_cycles(cycles: Any) -> list[Any]:
    """Extract cycles from supported result shapes."""
    if isinstance(cycles, dict):
        cycles = cycles.get("cycles", [])

    if isinstance(cycles, list):
        return cycles

    return []


def _get_functions(files: Any) -> list[dict[str, Any]]:
    """Extract function metadata from file analysis results."""
    if not isinstance(files, list):
        return []

    functions: list[dict[str, Any]] = []

    for file in files:
        if not isinstance(file, dict):
            continue

        file_functions = file.get("functions", [])

        if isinstance(file_functions, list):
            functions.extend(
                function
                for function in file_functions
                if isinstance(function, dict)
            )

    return functions


def _get_graph_edges(graph: Any) -> list[tuple[str, str]]:
    """Extract dependency edges from graph results."""
    if not isinstance(graph, dict):
        return []

    edges: list[tuple[str, str]] = []

    adjacency = graph.get("adjacency")

    if isinstance(adjacency, dict):
        for source, targets in adjacency.items():
            if not isinstance(source, str):
                continue

            if isinstance(targets, (set, list, tuple)):
                for target in targets:
                    if isinstance(target, str):
                        edges.append((source, target))

    raw_edges = graph.get("edges")

    if isinstance(raw_edges, list):
        for edge in raw_edges:
            if not isinstance(edge, dict):
                continue

            source = edge.get("from", edge.get("source"))
            target = edge.get("to", edge.get("target"))

            if isinstance(source, str) and isinstance(target, str):
                edges.append((source, target))

    return sorted(set(edges))


def _architecture_score(
    architecture: Any,
    cycles: Any,
) -> float:
    """
    Calculate Architecture DNA on a 0-100 scale.

    Formula:

        Architecture DNA =
            70% layer adherence
            + 30% cycle health

    Layer adherence starts at 100 and loses 10 points
    per architectural violation, with a minimum of 0.

    Cycle health starts at 100 and loses 15 points
    per dependency cycle, with a minimum of 0.

    The final score is:

        0.70 * layer_adherence + 0.30 * cycle_health
    """
    violations = _get_violations(architecture)
    cycle_list = _get_cycles(cycles)

    layer_adherence = _clamp(
        100.0 - (10.0 * len(violations))
    )

    cycle_health = _clamp(
        100.0 - (15.0 * len(cycle_list))
    )

    return _round_score(
        (0.70 * layer_adherence)
        + (0.30 * cycle_health)
    )


def _complexity_value(function: dict[str, Any]) -> float:
    """Extract cyclomatic complexity from a function record."""
    for key in (
        "complexity",
        "cyclomatic_complexity",
        "cc",
    ):
        value = function.get(key)

        if isinstance(value, (int, float)):
            return float(value)

    return 0.0


def _function_size(function: dict[str, Any]) -> float:
    """Extract function size from a function record."""
    for key in (
        "lines",
        "line_count",
        "loc",
        "size",
    ):
        value = function.get(key)

        if isinstance(value, (int, float)):
            return float(value)

    return 0.0


def _code_score(files: Any) -> float:
    """
    Calculate Code DNA on a 0-100 scale.

    Formula:

        complexity_score =
            100 - (average_complexity - 1) * 10

        size_score =
            100 - max_function_size

        threshold_score =
            100 - percentage_of_functions_over_threshold

        Code DNA =
            40% complexity_score
            + 30% threshold_score
            + 30% function_size_score

    Complexity is considered healthy at 1.
    Functions with complexity > 10 are considered
    over the complexity threshold.

    Function size is considered healthy up to 100 lines.

    All components are clamped to 0-100.
    """
    functions = _get_functions(files)

    if not functions:
        return 100.0

    complexities = [
        _complexity_value(function)
        for function in functions
    ]

    sizes = [
        _function_size(function)
        for function in functions
    ]

    average_complexity = (
        sum(complexities) / len(complexities)
    )

    max_size = max(sizes, default=0.0)

    over_threshold = sum(
        complexity > 10
        for complexity in complexities
    )

    percentage_over_threshold = (
        over_threshold / len(functions)
    ) * 100.0

    complexity_score = _clamp(
        100.0 - ((average_complexity - 1.0) * 10.0)
    )

    threshold_score = _clamp(
        100.0 - percentage_over_threshold
    )

    size_score = _clamp(
        100.0 - max(0.0, max_size - 100.0)
    )

    return _round_score(
        (0.40 * complexity_score)
        + (0.30 * threshold_score)
        + (0.30 * size_score)
    )


def _quality_score(
    graph: Any,
    cycles: Any,
) -> float:
    """
    Calculate Quality DNA on a 0-100 scale.

    Formula:

        coupling_score =
            100 - average_fan_out * 10

        cycle_score =
            100 - cycle_count * 15

        hotspot_score =
            100 - percentage_of_nodes_with_fan_out_above_5

        Quality DNA =
            40% coupling_score
            + 30% cycle_score
            + 30% hotspot_score

    Lower coupling, fewer cycles, and fewer hotspots
    produce higher quality scores.
    """
    edges = _get_graph_edges(graph)
    cycle_list = _get_cycles(cycles)

    nodes: set[str] = set()

    for source, target in edges:
        nodes.add(source)
        nodes.add(target)

    if not nodes:
        return 100.0

    fan_out: dict[str, int] = {
        node: 0 for node in nodes
    }

    fan_in: dict[str, int] = {
        node: 0 for node in nodes
    }

    for source, target in edges:
        fan_out[source] += 1
        fan_in[target] += 1

    average_fan_out = (
        sum(fan_out.values()) / len(nodes)
    )

    hotspot_count = sum(
        value > 5
        for value in fan_out.values()
    )

    hotspot_percentage = (
        hotspot_count / len(nodes)
    ) * 100.0

    coupling_score = _clamp(
        100.0 - (average_fan_out * 10.0)
    )

    cycle_score = _clamp(
        100.0 - (len(cycle_list) * 15.0)
    )

    hotspot_score = _clamp(
        100.0 - hotspot_percentage
    )

    return _round_score(
        (0.40 * coupling_score)
        + (0.30 * cycle_score)
        + (0.30 * hotspot_score)
    )


def calculate_dna_scores(
    *,
    files: Any = None,
    graph: Any = None,
    architecture: Any = None,
    cycles: Any = None,
) -> dict[str, float]:
    """
    Calculate the three Repo-DNA scores.

    Returns:

        {
            "architecture": 0-100,
            "code": 0-100,
            "quality": 0-100,
        }

    Each score is deterministic and independently clamped
    to the range 0-100.
    """
    return {
        "architecture": _architecture_score(
            architecture,
            cycles,
        ),
        "code": _code_score(files),
        "quality": _quality_score(
            graph,
            cycles,
        ),
    }


def score_dna(
    *,
    files: Any = None,
    graph: Any = None,
    architecture: Any = None,
    cycles: Any = None,
) -> dict[str, float]:
    """Public alias for calculating Repo-DNA scores."""
    return calculate_dna_scores(
        files=files,
        graph=graph,
        architecture=architecture,
        cycles=cycles,
    )