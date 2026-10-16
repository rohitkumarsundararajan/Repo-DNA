from __future__ import annotations

from pathlib import Path
from typing import Any


PATTERN_LAYERED = "Layered"
PATTERN_MVC = "MVC"
PATTERN_MICROSERVICES = "Microservices"
PATTERN_UNKNOWN = "Unknown"


def _layer_from_path(path: str) -> str:
    """Infer architecture layer from folder or filename."""
    parts = [part.lower() for part in Path(path).parts]
    filename = Path(path).stem.lower()

    keywords = {
        "controller": (
            "controller",
            "controllers",
            "route",
            "routes",
            "handler",
            "handlers",
        ),
        "service": (
            "service",
            "services",
            "usecase",
            "usecases",
        ),
        "repository": (
            "repository",
            "repositories",
            "dao",
            "model",
            "models",
            "db",
        ),
    }

    for layer, layer_keywords in keywords.items():
        for part in parts:
            if part in layer_keywords:
                return layer

        for keyword in layer_keywords:
            if keyword in filename:
                return layer

    return "unknown"


def _get_nodes(graph: Any) -> list[str]:
    """Get graph node paths from the existing DependencyGraph."""
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
    """Get adjacency data from the existing DependencyGraph."""
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


def _layered_evidence(
    nodes: list[str],
    adjacency: dict[str, set[str]],
) -> dict[str, Any] | None:
    layers = {path: _layer_from_path(path) for path in nodes}

    controller_files = [
        path for path, layer in layers.items()
        if layer == "controller"
    ]

    service_files = [
        path for path, layer in layers.items()
        if layer == "service"
    ]

    repository_files = [
        path for path, layer in layers.items()
        if layer == "repository"
    ]

    if not (
        controller_files
        and service_files
        and repository_files
    ):
        return None

    valid_edges = []
    for source, targets in adjacency.items():
        source_layer = layers.get(source)

        for target in sorted(targets):
            target_layer = layers.get(target)

            if (
                source_layer == "controller"
                and target_layer == "service"
            ) or (
                source_layer == "service"
                and target_layer == "repository"
            ):
                valid_edges.append(
                    {
                        "from": source,
                        "to": target,
                    }
                )

    if not valid_edges:
        return None

    return {
        "layers": {
            "controller": sorted(controller_files),
            "service": sorted(service_files),
            "repository": sorted(repository_files),
        },
        "edges": valid_edges,
    }


def _mvc_evidence(
    nodes: list[str],
    adjacency: dict[str, set[str]],
) -> dict[str, Any] | None:
    layers = {path: _layer_from_path(path) for path in nodes}

    controllers = [
        path for path, layer in layers.items()
        if layer == "controller"
    ]

    models = [
        path for path, layer in layers.items()
        if layer == "repository"
    ]

    views = [
        path for path in nodes
        if "view" in [part.lower() for part in Path(path).parts]
        or "view" in Path(path).stem.lower()
    ]

    if not (controllers and models and views):
        return None

    edges = []

    for source, targets in adjacency.items():
        for target in sorted(targets):
            if (
                source in controllers
                and (target in models or target in views)
            ):
                edges.append(
                    {
                        "from": source,
                        "to": target,
                    }
                )

    if not edges:
        return None

    return {
        "controllers": sorted(controllers),
        "models": sorted(models),
        "views": sorted(views),
        "edges": edges,
    }


def detect_pattern(graph: Any) -> dict[str, Any]:
    """
    Detect the repository architecture pattern.

    Detection order is deterministic:
    Layered -> MVC -> Microservices -> Unknown.

    Returns the detected pattern together with evidence.
    """
    nodes = sorted(_get_nodes(graph))
    adjacency = _get_adjacency(graph)

    layered = _layered_evidence(nodes, adjacency)

    if layered is not None:
        return {
            "pattern": PATTERN_LAYERED,
            "evidence": layered,
        }

    mvc = _mvc_evidence(nodes, adjacency)

    if mvc is not None:
        return {
            "pattern": PATTERN_MVC,
            "evidence": mvc,
        }

    return {
        "pattern": PATTERN_UNKNOWN,
        "evidence": {
            "reason": "No supported architecture pattern was detected.",
        },
    }