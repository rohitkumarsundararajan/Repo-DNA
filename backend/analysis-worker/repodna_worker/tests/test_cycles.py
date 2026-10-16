from repodna_worker.graph.builder import DependencyGraph, GraphNode
from repodna_worker.graph.cycles import CycleDetector, find_cycles


def make_graph(
    adjacency: dict[str, set[str]],
) -> DependencyGraph:
    """Create a DependencyGraph for testing."""

    nodes = {
        path: GraphNode(
            path=path,
            language="python",
            folder="src",
        )
        for path in adjacency
    }

    return DependencyGraph(
        adjacency=adjacency,
        nodes=nodes,
    )


def test_detect_simple_cycle() -> None:
    """Test detection of a simple A -> B -> A cycle."""

    graph = make_graph(
        {
            "A.py": {"B.py"},
            "B.py": {"A.py"},
        }
    )

    detector = CycleDetector()

    cycles = detector.find_cycles(graph)

    assert cycles == [
        ["A.py", "B.py"],
    ]


def test_detect_three_node_cycle() -> None:
    """Test detection of A -> B -> C -> A."""

    graph = make_graph(
        {
            "A.py": {"B.py"},
            "B.py": {"C.py"},
            "C.py": {"A.py"},
        }
    )

    cycles = find_cycles(graph)

    assert cycles == [
        ["A.py", "B.py", "C.py"],
    ]


def test_graph_without_cycle_returns_empty_list() -> None:
    """Test an acyclic graph."""

    graph = make_graph(
        {
            "A.py": {"B.py"},
            "B.py": {"C.py"},
            "C.py": set(),
        }
    )

    cycles = find_cycles(graph)

    assert cycles == []


def test_detect_multiple_cycles() -> None:
    """Test detection of multiple independent cycles."""

    graph = make_graph(
        {
            "A.py": {"B.py"},
            "B.py": {"A.py"},
            "C.py": {"D.py"},
            "D.py": {"C.py"},
        }
    )

    cycles = find_cycles(graph)

    assert cycles == [
        ["A.py", "B.py"],
        ["C.py", "D.py"],
    ]


def test_rotation_duplicates_are_removed() -> None:
    """
    Test that the same cycle is returned only once even when
    different traversal paths could represent the same cycle.
    """

    graph = make_graph(
        {
            "A.py": {"B.py"},
            "B.py": {"C.py"},
            "C.py": {"A.py"},
        }
    )

    cycles = find_cycles(graph)

    assert len(cycles) == 1
    assert cycles[0] == [
        "A.py",
        "B.py",
        "C.py",
    ]


def test_self_dependency_is_detected() -> None:
    """Test a node that depends on itself."""

    graph = make_graph(
        {
            "A.py": {"A.py"},
        }
    )

    cycles = find_cycles(graph)

    assert cycles == [
        ["A.py"],
    ]


def test_cycle_detection_is_deterministic() -> None:
    """Test that repeated runs return identical results."""

    graph = make_graph(
        {
            "C.py": {"A.py"},
            "A.py": {"B.py"},
            "B.py": {"C.py"},
        }
    )

    first = find_cycles(graph)
    second = find_cycles(graph)

    assert first == second
    assert first == [
        ["A.py", "B.py", "C.py"],
    ]