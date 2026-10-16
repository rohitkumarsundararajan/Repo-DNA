from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class MadgeError(RuntimeError):
    """Raised when Madge fails to generate a dependency graph."""


class MadgeRunner:
    """Run Madge and convert its output into a dependency graph."""

    def __init__(
        self,
        repo_root: str | Path,
        executable: str = "madge",
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.executable = executable

    def run_json(self) -> dict[str, list[str]]:
        """Run Madge --json and return its dependency map."""

        result = subprocess.run(
            [
                self.executable,
                "--json",
                str(self.repo_root),
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise MadgeError(
                "Madge failed while generating JSON output: "
                f"{result.stderr.strip()}"
            )

        try:
            data: Any = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MadgeError(
                "Madge returned invalid JSON output."
            ) from exc

        if not isinstance(data, dict):
            raise MadgeError(
                "Madge JSON output must be an object."
            )

        graph: dict[str, list[str]] = {}

        for source, targets in data.items():
            if not isinstance(source, str):
                continue

            if not isinstance(targets, list):
                continue

            graph[source] = [
                target
                for target in targets
                if isinstance(target, str)
            ]

        return graph

    def run_circular(self) -> list[list[str]]:
        """Run Madge --circular and return detected cycles."""

        result = subprocess.run(
            [
                self.executable,
                "--circular",
                str(self.repo_root),
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise MadgeError(
                "Madge failed while detecting circular dependencies: "
                f"{result.stderr.strip()}"
            )

        return self._parse_circular_output(result.stdout)

    def build_graph(self) -> dict[str, Any]:
        """Run Madge and return nodes, edges, and cycles."""

        dependency_map = self.run_json()
        cycles = self.run_circular()

        nodes: set[str] = set()
        edges: list[dict[str, str]] = []

        for source, targets in dependency_map.items():
            source_path = self._normalise_path(source)
            nodes.add(source_path)

            for target in targets:
                target_path = self._normalise_path(target)

                nodes.add(target_path)

                edges.append(
                    {
                        "source": source_path,
                        "target": target_path,
                    }
                )

        return {
            "nodes": sorted(nodes),
            "edges": edges,
            "cycles": cycles,
        }

    def _normalise_path(self, path: str) -> str:
        """Convert a Madge path into a stable POSIX-style path."""

        path = path.replace("\\", "/")

        try:
            absolute_path = (self.repo_root / path).resolve()
            return absolute_path.relative_to(
                self.repo_root
            ).as_posix()
        except ValueError:
            return Path(path).as_posix()

    def _parse_circular_output(
        self,
        output: str,
    ) -> list[list[str]]:
        """Parse Madge --circular text output."""

        cycles: list[list[str]] = []

        for line in output.splitlines():
            line = line.strip()

            if not line:
                continue

            # Madge circular output commonly looks like:
            #
            #   a.js -> b.js -> a.js
            #
            if "->" not in line:
                continue

            parts = [
                part.strip()
                for part in line.split("->")
                if part.strip()
            ]

            if len(parts) >= 2:
                cycles.append(
                    [
                        self._normalise_path(part)
                        for part in parts
                    ]
                )

        return cycles