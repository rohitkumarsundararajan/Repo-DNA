from pathlib import Path

import pytest

from repodna_worker.detect.buildtools import detect_build_tools
from repodna_worker.detect.frameworks import detect_frameworks


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fw(root):
    return {f.name for f in detect_frameworks(root)}


def _tools(root):
    return {(t.name, t.kind) for t in detect_build_tools(root)}


def test_package_json_frameworks_and_build_tools(tmp_path):
    _write(
        tmp_path,
        "package.json",
        '{"dependencies": {"react": "^18", "express": "^4"},'
        ' "devDependencies": {"vite": "^5"}}',
    )

    assert _fw(tmp_path) == {"React", "Express"}
    assert ("vite", "build_tool") in _tools(tmp_path)


def test_requirements_txt(tmp_path):
    _write(
        tmp_path,
        "requirements.txt",
        "Flask==2.3.0  # web\n# django-fake\n-r base.txt\nDjango>=4 ; python_version>'3.8'\nrequests\n",
    )

    assert _fw(tmp_path) == {"Flask", "Django"}
    assert ("pip", "package_manager") in _tools(tmp_path)


def test_pyproject_poetry_and_pep621(tmp_path):
    pytest.importorskip("tomllib")
    _write(
        tmp_path,
        "svc-a/pyproject.toml",
        '[tool.poetry.dependencies]\npython = "^3.11"\nfastapi = "^0.110"\n',
    )
    _write(
        tmp_path,
        "svc-b/pyproject.toml",
        '[project]\nname = "b"\ndependencies = ["Django>=4.2", "requests"]\n',
    )

    assert _fw(tmp_path) == {"FastAPI", "Django"}


def test_spring_boot_from_pom_and_gradle(tmp_path):
    _write(
        tmp_path,
        "a/pom.xml",
        "<project><parent><artifactId>spring-boot-starter-parent</artifactId>"
        "</parent></project>",
    )
    _write(
        tmp_path,
        "b/build.gradle",
        "plugins { id 'org.springframework.boot' version '3.2.0' }",
    )

    frameworks = detect_frameworks(tmp_path)
    assert [f.name for f in frameworks] == ["Spring Boot"]
    assert frameworks[0].source == "a/pom.xml"


def test_commented_out_spring_boot_in_pom_ignored(tmp_path):
    _write(
        tmp_path,
        "pom.xml",
        "<project><!-- <artifactId>spring-boot-starter</artifactId> -->"
        "<artifactId>plain-lib</artifactId></project>",
    )

    assert _fw(tmp_path) == set()


def test_package_managers_from_lockfiles(tmp_path):
    for name in ("package-lock.json", "yarn.lock", "poetry.lock", "pom.xml"):
        _write(tmp_path, name, "")

    assert _tools(tmp_path) == {
        ("npm", "package_manager"),
        ("yarn", "package_manager"),
        ("poetry", "package_manager"),
        ("maven", "package_manager"),
    }


def test_ignored_dirs_and_malformed_manifests(tmp_path):
    _write(tmp_path, "node_modules/x/package.json", '{"dependencies": {"react": "1"}}')
    _write(tmp_path, "venv/requirements.txt", "flask\n")
    _write(tmp_path, "package.json", "{not json")
    _write(tmp_path, "pyproject.toml", "= broken [")

    assert detect_frameworks(tmp_path) == []
    assert detect_build_tools(tmp_path) == []


def test_to_dict_shapes(tmp_path):
    _write(tmp_path, "package.json", '{"dependencies": {"next": "14"}}')
    _write(tmp_path, "yarn.lock")

    assert detect_frameworks(tmp_path)[0].to_dict() == {
        "name": "Next.js",
        "ecosystem": "javascript",
        "source": "package.json",
    }
    assert detect_build_tools(tmp_path)[0].to_dict() == {
        "name": "yarn",
        "kind": "package_manager",
        "source": "yarn.lock",
    }