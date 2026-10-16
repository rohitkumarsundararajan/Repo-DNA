from __future__ import annotations

from typing import Any

from repodna_worker.architecture.layers import classify_layer


RULE_CONTROLLER_TO_REPOSITORY = "controller_to_repository"
RULE_REPOSITORY_TO_SERVICE = "repository_to_service"
RULE_SERVICE_TO_CONTROLLER = "service_to_controller"


def _get_nodes(graph: Any) -> list[str]:
    """Get graph node paths from a DependencyGraph or dictionary."""

    if hasattr(graph, "nodes"):
        return list(graph.nodes.keys())

    if isinstance(graph, dict):
        nodes = graph.get("nodes", {})

        if isinstance(nodes, dict):
            return list(nodes.keys())

        if isinstance(nodes, list):
            result = []

            for node in nodes:
                if isinstance(node, str):
                    result.append(node)
                elif isinstance(node, dict) and "path" in node:
                    result.append(node["path"])

            return result

    return []


def _get_adjacency(graph: Any) -> dict[str, set[str]]:
    """Get adjacency data from a DependencyGraph or dictionary."""

    if hasattr(graph, "adjacency"):
        return graph.adjacency

    if isinstance(graph, dict):
        adjacency = graph.get("adjacency", {})

        if isinstance(adjacency, dict):
            return {
                source: set(targets)
                for source, targets in adjacency.items()
            }

        edges = graph.get("edges", [])
        result: dict[str, set[str]] = {}

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")

            if source and target:
                result.setdefault(source, set()).add(target)

        return result

    return {}


def detect_violations(graph: Any) -> dict[str, list[dict[str, str]]]:
    """
    Detect architectural boundary violations.

    Rules:
    - controller -> repository
    - repository -> service
    - service -> controller

    Returns exact source and target file paths for every violation.
    """

    nodes = _get_nodes(graph)
    adjacency = _get_adjacency(graph)

    layers = {
        path: classify_layer(path)
        for path in nodes
    }

    violations: list[dict[str, str]] = []

    for source in sorted(adjacency):
        source_layer = layers.get(source, "unknown")

        for target in sorted(adjacency[source]):
            target_layer = layers.get(target, "unknown")

            rule = None

            if (
                source_layer == "controller"
                and target_layer == "repository"
            ):
                rule = RULE_CONTROLLER_TO_REPOSITORY

            elif (
                source_layer == "repository"
                and target_layer == "service"
            ):
                rule = RULE_REPOSITORY_TO_SERVICE

            elif (
                source_layer == "service"
                and target_layer == "controller"
            ):
                rule = RULE_SERVICE_TO_CONTROLLER

            if rule is not None:
                violations.append(
                    {
                        "from": source,
                        "to": target,
                        "rule": rule,
                    }
                )

    return {
        "violations": violations,
    }