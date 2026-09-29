from repodna_worker.architecture.violations import detect_violations


def make_graph(nodes, edges):
    adjacency = {node: set() for node in nodes}

    for source, target in edges:
        adjacency[source].add(target)

    return {
        "nodes": nodes,
        "adjacency": adjacency,
    }


def test_controller_directly_to_repository():
    graph = make_graph(
        [
            "controllers/UserController.py",
            "repositories/UserRepository.py",
        ],
        [
            (
                "controllers/UserController.py",
                "repositories/UserRepository.py",
            ),
        ],
    )

    result = detect_violations(graph)
    violations = result["violations"]

    assert violations[0] == {
    "from": "controllers/UserController.py",
    "to": "repositories/UserRepository.py",
    "rule": "controller_to_repository",
}


def test_repository_to_service_reverse_edge():
    graph = make_graph(
        [
            "repositories/UserRepository.py",
            "services/UserService.py",
        ],
        [
            (
                "repositories/UserRepository.py",
                "services/UserService.py",
            ),
        ],
    )

    result = detect_violations(graph)
    violations = result["violations"]

    assert violations[0] == {
    "from": "repositories/UserRepository.py",
    "to": "services/UserService.py",
    "rule": "repository_to_service",
}


def test_service_to_controller_reverse_edge():
    graph = make_graph(
        [
            "services/UserService.py",
            "controllers/UserController.py",
        ],
        [
            (
                "services/UserService.py",
                "controllers/UserController.py",
            ),
        ],
    )

    result = detect_violations(graph)
    violations = result["violations"]

    assert violations[0] == {
    "from": "services/UserService.py",
    "to": "controllers/UserController.py",
    "rule": "service_to_controller",
}


def test_valid_layered_edges_have_no_violations():
    graph = make_graph(
        [
            "controllers/UserController.py",
            "services/UserService.py",
            "repositories/UserRepository.py",
        ],
        [
            (
                "controllers/UserController.py",
                "services/UserService.py",
            ),
            (
                "services/UserService.py",
                "repositories/UserRepository.py",
            ),
        ],
    )

    assert detect_violations(graph)["violations"] == []


def test_deterministic_output():
    graph = make_graph(
        [
            "controllers/UserController.py",
            "repositories/UserRepository.py",
            "services/UserService.py",
        ],
        [
            (
                "controllers/UserController.py",
                "repositories/UserRepository.py",
            ),
            (
                "services/UserService.py",
                "repositories/UserRepository.py",
            ),
        ],
    )

    first = detect_violations(graph)
    second = detect_violations(graph)

    assert first == second