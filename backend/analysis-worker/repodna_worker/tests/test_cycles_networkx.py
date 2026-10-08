import networkx as nx

from repodna_worker.graph.builder import DependencyGraph, GraphNode
from repodna_worker.graph.cycles import find_cycles


def make_graph(edges):
    nodes = set()

    for source, target in edges:
        nodes.add(source)
        nodes.add(target)

    graph = DependencyGraph()

    for node in sorted(nodes):
        graph.nodes[node] = GraphNode(
            path=node,
            language="Python",
            folder="",
        )
        graph.adjacency[node] = set()

    for source, target in edges:
        graph.adjacency[source].add(target)

    return graph


def normalize_cycles(cycles):
    normalized = set()

    for cycle in cycles:
        if not cycle:
            continue

        rotations = [
            tuple(cycle[index:] + cycle[:index])
            for index in range(len(cycle))
        ]

        normalized.add(min(rotations))

    return normalized


def test_repo_dna_cycles_match_networkx():
    edges = [
        ("A.py", "B.py"),
        ("B.py", "C.py"),
        ("C.py", "A.py"),
        ("D.py", "E.py"),
    ]

    graph = make_graph(edges)

    repo_dna_cycles = find_cycles(graph)

    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from(edges)

    networkx_cycles = [
        list(cycle)
        for cycle in nx.simple_cycles(nx_graph)
    ]

    assert normalize_cycles(repo_dna_cycles) == normalize_cycles(
        networkx_cycles
    )


def test_self_loop_matches_networkx():
    edges = [
        ("A.py", "A.py"),
        ("B.py", "C.py"),
    ]

    graph = make_graph(edges)

    repo_dna_cycles = find_cycles(graph)

    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from(edges)

    networkx_cycles = [
        list(cycle)
        for cycle in nx.simple_cycles(nx_graph)
    ]

    assert normalize_cycles(repo_dna_cycles) == normalize_cycles(
        networkx_cycles
    )
