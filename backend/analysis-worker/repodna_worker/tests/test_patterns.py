from repodna_worker.architecture.patterns import detect_pattern


def make_graph(nodes, edges):
    adjacency = {node: set() for node in nodes}

    for source, target in edges:
        adjacency[source].add(target)

    return {
        "nodes": nodes,
        "adjacency": adjacency,
    }


def test_layered_pattern():
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

    result = detect_pattern(graph)

    assert result["pattern"] == "Layered"
    assert result["evidence"]["edges"]


def test_mvc_pattern():
    graph = make_graph(
        [
            "controllers/UserController.py",
            "models/User.py",
            "views/UserView.py",
        ],
        [
            (
                "controllers/UserController.py",
                "models/User.py",
            ),
            (
                "controllers/UserController.py",
                "views/UserView.py",
            ),
        ],
    )

    result = detect_pattern(graph)

    assert result["pattern"] == "MVC"
    assert result["evidence"]["edges"]


def test_unknown_pattern():
    graph = make_graph(
        [
            "utils/helper.py",
            "config/settings.py",
        ],
        [
            (
                "utils/helper.py",
                "config/settings.py",
            ),
        ],
    )

    result = detect_pattern(graph)

    assert result["pattern"] == "Unknown"


def test_deterministic_output():
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

    first = detect_pattern(graph)
    second = detect_pattern(graph)

    assert first == second