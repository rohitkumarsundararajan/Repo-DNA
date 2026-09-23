from pathlib import Path

from repodna_worker.graph.resolver import ImportResolver
from repodna_worker.parsing.models import ImportInfo, ParsedFile


def test_resolve_python_absolute_import(tmp_path: Path) -> None:
    """Test resolving a Python absolute import."""

    repository = tmp_path / "repo"

    user_service = (
        repository / "src" / "service" / "UserService.py"
    )

    user_service.parent.mkdir(parents=True)
    user_service.write_text("# test file")

    parsed_file = ParsedFile(
        path="src/controller/UserController.py",
        language="python",
        loc=20,
    )

    import_info = ImportInfo(
        module="src.service.UserService",
        names=["UserService"],
        is_relative=False,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == user_service.resolve()


def test_resolve_python_relative_import(tmp_path: Path) -> None:
    """Test resolving a Python relative import."""

    repository = tmp_path / "repo"

    controller = (
        repository / "src" / "controller" / "UserController.py"
    )

    user_service = (
        repository / "src" / "controller" / "UserService.py"
    )

    controller.parent.mkdir(parents=True)
    controller.write_text("# controller")
    user_service.write_text("# service")

    parsed_file = ParsedFile(
        path="src/controller/UserController.py",
        language="python",
        loc=20,
    )

    import_info = ImportInfo(
        module="UserService",
        names=["UserService"],
        is_relative=True,
        level=1,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == user_service.resolve()


def test_resolve_python_package_init(tmp_path: Path) -> None:
    """Test resolving a Python package through __init__.py."""

    repository = tmp_path / "repo"

    package_init = (
        repository
        / "src"
        / "service"
        / "__init__.py"
    )

    package_init.parent.mkdir(parents=True)
    package_init.write_text("# service package")

    parsed_file = ParsedFile(
        path="src/controller/UserController.py",
        language="python",
        loc=20,
    )

    import_info = ImportInfo(
        module="src.service",
        names=["service"],
        is_relative=False,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == package_init.resolve()
def test_resolve_typescript_relative_import(tmp_path: Path) -> None:
    """Test resolving a TypeScript relative import."""

    repository = tmp_path / "repo"

    user_component = (
        repository
        / "src"
        / "components"
        / "User.tsx"
    )

    user_service = (
        repository
        / "src"
        / "components"
        / "UserService.ts"
    )

    user_component.parent.mkdir(parents=True)
    user_component.write_text("// User component")
    user_service.write_text("// User service")

    parsed_file = ParsedFile(
        path="src/components/User.tsx",
        language="typescript",
        loc=30,
    )

    import_info = ImportInfo(
        module="./UserService",
        names=["UserService"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == user_service.resolve()
def test_resolve_typescript_index_import(tmp_path: Path) -> None:
    """Test resolving a TypeScript directory import through index.ts."""

    repository = tmp_path / "repo"

    user_component = (
        repository
        / "src"
        / "components"
        / "User.tsx"
    )

    index_file = (
        repository
        / "src"
        / "components"
        / "UserService"
        / "index.ts"
    )

    user_component.parent.mkdir(parents=True)
    user_component.write_text("// User component")

    index_file.parent.mkdir(parents=True)
    index_file.write_text("// User service index")

    parsed_file = ParsedFile(
        path="src/components/User.tsx",
        language="typescript",
        loc=30,
    )

    import_info = ImportInfo(
        module="./UserService",
        names=["UserService"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == index_file.resolve()
def test_ignore_external_javascript_package(tmp_path: Path) -> None:
    """Test that external JavaScript packages are not resolved."""

    repository = tmp_path / "repo"

    parsed_file = ParsedFile(
        path="src/components/User.tsx",
        language="typescript",
        loc=30,
    )

    import_info = ImportInfo(
        module="react",
        names=["useState"],
        is_relative=False,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result is None
def test_resolve_typescript_parent_relative_import(tmp_path: Path) -> None:
    """Test resolving a TypeScript parent-directory relative import."""

    repository = tmp_path / "repo"

    user_component = (
        repository
        / "src"
        / "components"
        / "User.tsx"
    )

    helper_file = (
        repository
        / "src"
        / "utils"
        / "helper.ts"
    )

    user_component.parent.mkdir(parents=True)
    user_component.write_text("// User component")

    helper_file.parent.mkdir(parents=True)
    helper_file.write_text("// helper")

    parsed_file = ParsedFile(
        path="src/components/User.tsx",
        language="typescript",
        loc=30,
    )

    import_info = ImportInfo(
        module="../utils/helper",
        names=["helper"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == helper_file.resolve()
def test_resolve_javascript_relative_import(tmp_path: Path) -> None:
    """Test resolving a JavaScript relative import."""

    repository = tmp_path / "repo"

    app_file = (
        repository
        / "src"
        / "app.js"
    )

    helper_file = (
        repository
        / "src"
        / "utils"
        / "helper.js"
    )

    app_file.parent.mkdir(parents=True)
    app_file.write_text("// app")

    helper_file.parent.mkdir(parents=True)
    helper_file.write_text("// helper")

    parsed_file = ParsedFile(
        path="src/app.js",
        language="javascript",
        loc=20,
    )

    import_info = ImportInfo(
        module="./utils/helper",
        names=["helper"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == helper_file.resolve()
def test_resolve_javascript_relative_import(tmp_path: Path) -> None:
    """Test resolving a JavaScript relative import."""

    repository = tmp_path / "repo"

    app_file = (
        repository
        / "src"
        / "app.js"
    )

    helper_file = (
        repository
        / "src"
        / "utils"
        / "helper.js"
    )

    app_file.parent.mkdir(parents=True)
    app_file.write_text("// app")

    helper_file.parent.mkdir(parents=True)
    helper_file.write_text("// helper")

    parsed_file = ParsedFile(
        path="src/app.js",
        language="javascript",
        loc=20,
    )

    import_info = ImportInfo(
        module="./utils/helper",
        names=["helper"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == helper_file.resolve()
def test_resolve_tsx_relative_import(tmp_path: Path) -> None:
    """Test resolving a TSX relative import."""

    repository = tmp_path / "repo"

    app_file = (
        repository
        / "src"
        / "components"
        / "App.tsx"
    )

    button_file = (
        repository
        / "src"
        / "components"
        / "Button.tsx"
    )

    app_file.parent.mkdir(parents=True)
    app_file.write_text("// App component")
    button_file.write_text("// Button component")

    parsed_file = ParsedFile(
        path="src/components/App.tsx",
        language="typescript",
        loc=25,
    )

    import_info = ImportInfo(
        module="./Button",
        names=["Button"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )
    assert result == button_file.resolve()
def test_resolve_javascript_index_import(tmp_path: Path) -> None:
    """Test resolving a JavaScript directory import through index.js."""

    repository = tmp_path / "repo"

    app_file = (
        repository
        / "src"
        / "app.js"
    )

    index_file = (
        repository
        / "src"
        / "utils"
        / "index.js"
    )

    app_file.parent.mkdir(parents=True)
    app_file.write_text("// app")

    index_file.parent.mkdir(parents=True)
    index_file.write_text("// utils index")

    parsed_file = ParsedFile(
        path="src/app.js",
        language="javascript",
        loc=20,
    )

    import_info = ImportInfo(
        module="./utils",
        names=["utils"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == index_file.resolve()
def test_resolve_tsx_index_import(tmp_path: Path) -> None:
    """Test resolving a TSX directory import through index.tsx."""

    repository = tmp_path / "repo"

    app_file = (
        repository
        / "src"
        / "components"
        / "App.tsx"
    )

    index_file = (
        repository
        / "src"
        / "components"
        / "Button"
        / "index.tsx"
    )

    app_file.parent.mkdir(parents=True)
    app_file.write_text("// App")

    index_file.parent.mkdir(parents=True)
    index_file.write_text("// Button")

    parsed_file = ParsedFile(
        path="src/components/App.tsx",
        language="typescript",
        loc=25,
    )

    import_info = ImportInfo(
        module="./Button",
        names=["Button"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result == index_file.resolve()
def test_unresolved_javascript_import_returns_none(tmp_path: Path) -> None:
    """Test that an unresolved JavaScript import returns None."""

    repository = tmp_path / "repo"

    app_file = (
        repository
        / "src"
        / "app.js"
    )

    app_file.parent.mkdir(parents=True)
    app_file.write_text("// app")

    parsed_file = ParsedFile(
        path="src/app.js",
        language="javascript",
        loc=20,
    )

    import_info = ImportInfo(
        module="./doesNotExist",
        names=["doesNotExist"],
        is_relative=True,
        level=0,
    )

    resolver = ImportResolver(repository)

    result = resolver.resolve_import(
        parsed_file,
        import_info,
    )

    assert result is None