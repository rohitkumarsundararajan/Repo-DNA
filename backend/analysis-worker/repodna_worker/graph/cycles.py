from __future__ import annotations

from dataclasses import dataclass

from repodna_worker.graph.builder import DependencyGraph


@dataclass
class CycleDetector:
    """Detect circular dependencies in a dependency graph."""

    def find_cycles(self, graph: DependencyGraph) -> list[list[str]]:
        """
        Find all dependency cycles using iterative DFS.

        Returns:
            A deterministic list of cycles. Each cycle is represented
            as an ordered list of node paths.
        """

        # 0 = white (unvisited)
        # 1 = grey  (currently in DFS stack)
        # 2 = black (fully processed)
        colour: dict[str, int] = {
            node: 0 for node in graph.adjacency
        }

        cycles: set[tuple[str, ...]] = set()

        for start in sorted(graph.adjacency):
            if colour[start] != 0:
                continue

            self._dfs_iterative(
                graph=graph,
                start=start,
                colour=colour,
                cycles=cycles,
            )

        return [
            list(cycle)
            for cycle in sorted(cycles)
        ]

    def _dfs_iterative(
        self,
        graph: DependencyGraph,
        start: str,
        colour: dict[str, int],
        cycles: set[tuple[str, ...]],
    ) -> None:
        """Perform iterative DFS from one starting node."""

        # Stack entries:
        #
        # (node, iterator, path)
        #
        # The iterator allows us to emulate recursive DFS without
        # using Python's recursion stack.
        stack: list[
            tuple[str, object, list[str]]
        ] = []

        colour[start] = 1

        neighbours = iter(
            sorted(graph.adjacency.get(start, set()))
        )

        stack.append(
            (
                start,
                neighbours,
                [start],
            )
        )

        while stack:
            node, neighbours, path = stack[-1]

            try:
                neighbour = next(neighbours)
            except StopIteration:
                # Finished processing this node.
                colour[node] = 2
                stack.pop()
                continue

            if colour.get(neighbour, 0) == 0:
                # White node:
                # continue DFS.
                colour[neighbour] = 1

                child_neighbours = iter(
                    sorted(
                        graph.adjacency.get(
                            neighbour,
                            set(),
                        )
                    )
                )

                stack.append(
                    (
                        neighbour,
                        child_neighbours,
                        path + [neighbour],
                    )
                )

            elif colour.get(neighbour, 0) == 1:
                # Grey node means that we found a back edge.
                #
                # Example:
                #
                # A -> B -> C -> A
                #
                # Current path:
                # [A, B, C]
                #
                # neighbour:
                # A
                #
                # Cycle:
                # [A, B, C]
                try:
                    cycle_start = path.index(neighbour)
                except ValueError:
                    continue

                cycle = path[cycle_start:]

                canonical = self._canonical_cycle(cycle)

                cycles.add(canonical)

    def _canonical_cycle(
        self,
        cycle: list[str],
    ) -> tuple[str, ...]:
        """
        Normalize a cycle so rotations represent the same cycle.

        Example:

            [A, B, C]
            [B, C, A]
            [C, A, B]

        all become:

            (A, B, C)
        """

        if not cycle:
            return ()

        rotations = [
            tuple(
                cycle[index:] + cycle[:index]
            )
            for index in range(len(cycle))
        ]

        return min(rotations)


def find_cycles(
    graph: DependencyGraph,
) -> list[list[str]]:
    """Convenience function for cycle detection."""

    detector = CycleDetector()

    return detector.find_cycles(graph)