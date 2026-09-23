from pathlib import Path

from repodna_worker.graph.builder import GraphBuilder
from repodna_worker.parsing.models import ImportInfo, ParsedFile


def test_build_layered_dependency_graph(tmp_path: Path) -> None:
    """Test building a simple controller -> service -> repository graph."""

    repository = tmp_path / "repo"

    controller = repository / "src" / "controller" / "UserController.py"
    service = repository / "src" / "service" / "UserService.py"
    repo = repository / "src" / "repository" / "UserRepository.py"

    controller.parent.mkdir(parents=True)
    service.parent.mkdir(parents=True)
    repo.parent.mkdir(parents=True)

    controller.write_text("# controller")
    service.write_text("# service")
    repo.write_text("# repository")

    parsed_files = [
        ParsedFile(
            path="src/controller/UserController.py",
            language="python",
            loc=20,
            imports=[
                ImportInfo(
                    module="src.service.UserService",
                    names=["UserService"],
                    is_relative=False,
                    level=0,
                )
            ],
        ),
        ParsedFile(
            path="src/service/UserService.py",
            language="python",
            loc=25,
            imports=[
                ImportInfo(
                    module="src.repository.UserRepository",
                    names=["UserRepository"],
                    is_relative=False,
                    level=0,
                )
            ],
        ),
        ParsedFile(
            path="src/repository/UserRepository.py",
            language="python",
            loc=15,
        ),
    ]

    builder = GraphBuilder(repository)
    graph = builder.build(parsed_files)

    assert graph.adjacency == {
        "src/controller/UserController.py": {
            "src/service/UserService.py"
        },
        "src/service/UserService.py": {
            "src/repository/UserRepository.py"
        },
        "src/repository/UserRepository.py": set(),
    }

    assert graph.nodes[
        "src/controller/UserController.py"
    ].fan_out == 1

    assert graph.nodes[
        "src/controller/UserController.py"
    ].fan_in == 0

    assert graph.nodes[
        "src/service/UserService.py"
    ].fan_in == 1

    assert graph.nodes[
        "src/service/UserService.py"
    ].fan_out == 1

    assert graph.nodes[
        "src/repository/UserRepository.py"
    ].fan_in == 1

    assert graph.nodes[
        "src/repository/UserRepository.py"
    ].fan_out == 0


def test_graph_export_contains_nodes_and_edges(tmp_path: Path) -> None:
    """Test exporting the graph into nodes[] and edges[]."""

    repository = tmp_path / "repo"

    controller = repository / "src" / "controller" / "UserController.py"
    service = repository / "src" / "service" / "UserService.py"

    controller.parent.mkdir(parents=True)
    service.parent.mkdir(parents=True)

    controller.write_text("# controller")
    service.write_text("# service")

    parsed_files = [
        ParsedFile(
            path="src/controller/UserController.py",
            language="python",
            loc=20,
            imports=[
                ImportInfo(
                    module="src.service.UserService",
                    names=["UserService"],
                    is_relative=False,
                    level=0,
                )
            ],
        ),
        ParsedFile(
            path="src/service/UserService.py",
            language="python",
            loc=25,
        ),
    ]

    builder = GraphBuilder(repository)
    graph = builder.build(parsed_files)

    exported = graph.to_dict()

    assert "nodes" in exported
    assert "edges" in exported

    assert len(exported["nodes"]) == 2
    assert len(exported["edges"]) == 1

    assert exported["edges"][0] == {
        "source": "src/controller/UserController.py",
        "target": "src/service/UserService.py",
    }
def test_graph_calculates_fan_in_and_fan_out(tmp_path: Path) -> None:
    """Test fan-in and fan-out when multiple files depend on the same file."""

    repository = tmp_path / "repo"

    controller = repository / "src" / "controller" / "UserController.py"
    admin_controller = (
        repository / "src" / "controller" / "AdminController.py"
    )
    service = repository / "src" / "service" / "UserService.py"
    repository_file = (
        repository / "src" / "repository" / "UserRepository.py"
    )

    controller.parent.mkdir(parents=True, exist_ok=True)
    admin_controller.parent.mkdir(parents=True, exist_ok=True)
    service.parent.mkdir(parents=True, exist_ok=True)
    repository_file.parent.mkdir(parents=True, exist_ok=True)

    controller.write_text("# controller")
    admin_controller.write_text("# admin controller")
    service.write_text("# service")
    repository_file.write_text("# repository")

    parsed_files = [
        ParsedFile(
            path="src/controller/UserController.py",
            language="python",
            loc=20,
            imports=[
                ImportInfo(
                    module="src.service.UserService",
                    names=["UserService"],
                    is_relative=False,
                    level=0,
                )
            ],
        ),
        ParsedFile(
            path="src/controller/AdminController.py",
            language="python",
            loc=20,
            imports=[
                ImportInfo(
                    module="src.service.UserService",
                    names=["UserService"],
                    is_relative=False,
                    level=0,
                )
            ],
        ),
        ParsedFile(
            path="src/service/UserService.py",
            language="python",
            loc=25,
            imports=[
                ImportInfo(
                    module="src.repository.UserRepository",
                    names=["UserRepository"],
                    is_relative=False,
                    level=0,
                )
            ],
        ),
        ParsedFile(
            path="src/repository/UserRepository.py",
            language="python",
            loc=15,
        ),
    ]

    builder = GraphBuilder(repository)
    graph = builder.build(parsed_files)

    user_controller = graph.nodes[
        "src/controller/UserController.py"
    ]

    admin_controller_node = graph.nodes[
        "src/controller/AdminController.py"
    ]

    user_service = graph.nodes[
        "src/service/UserService.py"
    ]

    user_repository = graph.nodes[
        "src/repository/UserRepository.py"
    ]

    assert user_controller.fan_in == 0
    assert user_controller.fan_out == 1

    assert admin_controller_node.fan_in == 0
    assert admin_controller_node.fan_out == 1

    assert user_service.fan_in == 2
    assert user_service.fan_out == 1

    assert user_repository.fan_in == 1
    assert user_repository.fan_out == 0
def test_graph_keeps_isolated_file(tmp_path: Path) -> None:
    """Test that a file with no dependencies remains in the graph."""

    repository = tmp_path / "repo"

    isolated_file = (
        repository / "src" / "utils" / "constants.py"
    )

    isolated_file.parent.mkdir(parents=True)
    isolated_file.write_text("# constants")

    parsed_files = [
        ParsedFile(
            path="src/utils/constants.py",
            language="python",
            loc=10,
        ),
    ]

    builder = GraphBuilder(repository)
    graph = builder.build(parsed_files)

    assert "src/utils/constants.py" in graph.nodes
    assert graph.adjacency["src/utils/constants.py"] == set()

    node = graph.nodes["src/utils/constants.py"]

    assert node.fan_in == 0
    assert node.fan_out == 0
    assert node.language == "python"
    assert node.folder == "src/utils"
def test_graph_ignores_unresolved_external_imports(tmp_path: Path) -> None:
    """Test that unresolved/external imports do not create graph edges."""

    repository = tmp_path / "repo"

    app_file = repository / "src" / "app.py"

    app_file.parent.mkdir(parents=True)
    app_file.write_text("# app")

    parsed_files = [
        ParsedFile(
            path="src/app.py",
            language="python",
            loc=20,
            imports=[
                ImportInfo(
                    module="requests",
                    names=[],
                    is_relative=False,
                    level=0,
                ),
                ImportInfo(
                    module="flask",
                    names=["Flask"],
                    is_relative=False,
                    level=0,
                ),
            ],
        ),
    ]

    builder = GraphBuilder(repository)
    graph = builder.build(parsed_files)

    assert graph.adjacency["src/app.py"] == set()

    assert graph.nodes["src/app.py"].fan_in == 0
    assert graph.nodes["src/app.py"].fan_out == 0

    assert len(graph.nodes) == 1
def test_graph_deduplicates_duplicate_imports(tmp_path: Path) -> None:
    """Test that duplicate imports create only one graph edge."""

    repository = tmp_path / "repo"

    app_file = repository / "src" / "app.py"
    helper_file = repository / "src" / "utils" / "helper.py"

    app_file.parent.mkdir(parents=True)
    helper_file.parent.mkdir(parents=True)

    app_file.write_text("# app")
    helper_file.write_text("# helper")

    parsed_files = [
        ParsedFile(
            path="src/app.py",
            language="python",
            loc=20,
            imports=[
                ImportInfo(
                    module="src.utils.helper",
                    names=["helper"],
                    is_relative=False,
                    level=0,
                ),
                ImportInfo(
                    module="src.utils.helper",
                    names=["helper"],
                    is_relative=False,
                    level=0,
                ),
            ],
        ),
        ParsedFile(
            path="src/utils/helper.py",
            language="python",
            loc=10,
        ),
    ]

    builder = GraphBuilder(repository)
    graph = builder.build(parsed_files)

    assert graph.adjacency["src/app.py"] == {
        "src/utils/helper.py"
    }

    assert len(graph.adjacency["src/app.py"]) == 1

    assert graph.nodes["src/app.py"].fan_out == 1
    assert graph.nodes["src/utils/helper.py"].fan_in == 1
def test_graph_export_node_metadata(tmp_path: Path) -> None:
    """Test that exported nodes contain all required metadata."""

    repository = tmp_path / "repo"

    app_file = repository / "src" / "app.py"

    app_file.parent.mkdir(parents=True)
    app_file.write_text("# app")

    parsed_files = [
        ParsedFile(
            path="src/app.py",
            language="python",
            loc=20,
        ),
    ]

    builder = GraphBuilder(repository)
    graph = builder.build(parsed_files)

    exported = graph.to_dict()

    assert len(exported["nodes"]) == 1

    node = exported["nodes"][0]

    assert node == {
        "path": "src/app.py",
        "language": "python",
        "folder": "src",
        "fan_in": 0,
        "fan_out": 0,
    }
def test_graph_build_is_deterministic(tmp_path: Path) -> None:
    """Test that repeated builds produce the same graph."""

    repository = tmp_path / "repo"

    app_file = repository / "src" / "app.py"
    helper_file = repository / "src" / "utils" / "helper.py"

    app_file.parent.mkdir(parents=True)
    helper_file.parent.mkdir(parents=True)

    app_file.write_text("# app")
    helper_file.write_text("# helper")

    parsed_files = [
        ParsedFile(
            path="src/app.py",
            language="python",
            loc=20,
            imports=[
                ImportInfo(
                    module="src.utils.helper",
                    names=["helper"],
                    is_relative=False,
                    level=0,
                )
            ],
        ),
        ParsedFile(
            path="src/utils/helper.py",
            language="python",
            loc=10,
        ),
    ]

    builder = GraphBuilder(repository)

    first_graph = builder.build(parsed_files)
    second_graph = builder.build(parsed_files)

    assert first_graph.to_dict() == second_graph.to_dict()

    assert first_graph.adjacency == second_graph.adjacency
    assert first_graph.nodes.keys() == second_graph.nodes.keys()
def test_graph_ignores_resolved_files_not_in_parsed_files(
    tmp_path: Path,
) -> None:
    """Test that resolved files outside the parsed file set are ignored."""

    repository = tmp_path / "repo"

    app_file = repository / "src" / "app.py"
    helper_file = repository / "src" / "utils" / "helper.py"

    app_file.parent.mkdir(parents=True)
    helper_file.parent.mkdir(parents=True)

    app_file.write_text("# app")
    helper_file.write_text("# helper")

    parsed_files = [
        ParsedFile(
            path="src/app.py",
            language="python",
            loc=20,
            imports=[
                ImportInfo(
                    module="src.utils.helper",
                    names=["helper"],
                    is_relative=False,
                    level=0,
                )
            ],
        ),
    ]

    builder = GraphBuilder(repository)
    graph = builder.build(parsed_files)

    assert "src/app.py" in graph.nodes

    assert "src/utils/helper.py" not in graph.nodes

    assert graph.adjacency["src/app.py"] == set()

    assert graph.nodes["src/app.py"].fan_out == 0