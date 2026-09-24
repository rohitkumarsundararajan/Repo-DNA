from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from repodna_worker.graph.resolver import ImportResolver
from repodna_worker.parsing.models import ParsedFile


@dataclass
class GraphNode:
    path: str
    language: str
    folder: str
    fan_in: int = 0
    fan_out: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "language": self.language,
            "folder": self.folder,
            "fan_in": self.fan_in,
            "fan_out": self.fan_out,
        }


@dataclass
class DependencyGraph:
    adjacency: dict[str, set[str]] = field(default_factory=dict)
    nodes: dict[str, GraphNode] = field(default_factory=dict)

    def to_dict(self) -> dict:
        edges = []

        for source, targets in self.adjacency.items():
            for target in sorted(targets):
                edges.append(
                    {
                        "source": source,
                        "target": target,
                    }
                )

        return {
            "nodes": [
                node.to_dict()
                for node in self.nodes.values()
            ],
            "edges": edges,
        }


class GraphBuilder:
    """Build the repository dependency graph once."""

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.resolver = ImportResolver(self.repo_root)

    def build(
        self,
        parsed_files: list[ParsedFile],
    ) -> DependencyGraph:
        """Build the complete dependency graph."""

        graph = DependencyGraph()

        # Create all nodes first.
        for parsed_file in parsed_files:
            path = self._normalise_path(parsed_file.path)

            graph.nodes[path] = GraphNode(
                path=path,
                language=parsed_file.language,
                folder=(Path(path).parent.as_posix()),
            )

            graph.adjacency[path] = set()

        # Resolve imports and create edges.
        for parsed_file in parsed_files:
            source = self._normalise_path(parsed_file.path)

            for import_info in parsed_file.imports:
                resolved = self.resolver.resolve_import(
                    parsed_file,
                    import_info,
                )

                if resolved is None:
                    continue

                target = self._relative_path(resolved)

                # Only include files that are part of this graph.
                if target not in graph.nodes:
                    continue

                graph.adjacency[source].add(target)

        # Calculate fan-in and fan-out.
        for source, targets in graph.adjacency.items():
            graph.nodes[source].fan_out = len(targets)

            for target in targets:
                graph.nodes[target].fan_in += 1

        return graph

    def _normalise_path(self, path: str | Path) -> str:
        """Convert a repository path into a stable POSIX-style path."""

        return Path(path).as_posix()

    def _relative_path(self, path: Path) -> str:
        """Convert an absolute path into a repository-relative path."""

        return path.resolve().relative_to(self.repo_root).as_posix()