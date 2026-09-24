"""Framework detection by reading dependency manifests.

Only reads package.json, requirements*.txt, pyproject.toml, pom.xml and
build.gradle(.kts). Never runs install or build scripts.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

from ._fs import iter_files, package_json_deps, read_text

JS_FRAMEWORKS = {
    "react": "React",
    "next": "Next.js",
    "vue": "Vue",
    "nuxt": "Nuxt",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "express": "Express",
    "@nestjs/core": "NestJS",
    "fastify": "Fastify",
    "koa": "Koa",
}

PY_FRAMEWORKS = {
    "flask": "Flask",
    "django": "Django",
    "fastapi": "FastAPI",
}

_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_XML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ARTIFACT_ID = re.compile(r"<artifactId>\s*([^<\s]+)\s*</artifactId>")
_GRADLE_SPRING_BOOT = re.compile(r"org\.springframework\.boot|spring-boot")


@dataclass(frozen=True)
class Framework:
    name: str
    ecosystem: str  # "javascript" | "python" | "java"
    source: str  # manifest path relative to the repo root (posix)

    def to_dict(self) -> dict:
        return {"name": self.name, "ecosystem": self.ecosystem, "source": self.source}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _spec_name(spec: object) -> str | None:
    if not isinstance(spec, str):
        return None
    match = _REQ_NAME.match(spec)
    return _normalize(match.group(1)) if match else None


def _requirements_names(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = _spec_name(line)
        if name:
            names.add(name)
    return names


def _pyproject_names(text: str) -> set[str]:
    if tomllib is None:
        return set()
    try:
        data = tomllib.loads(text)
    except ValueError:
        return set()

    names: set[str] = set()

    def add_specs(specs: object) -> None:
        if isinstance(specs, list):
            names.update(n for n in map(_spec_name, specs) if n)

    def add_keys(deps: object) -> None:
        if isinstance(deps, dict):
            names.update(_normalize(k) for k in deps)

    project = data.get("project")
    if isinstance(project, dict):
        add_specs(project.get("dependencies"))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for specs in optional.values():
                add_specs(specs)

    tool = data.get("tool")
    poetry = tool.get("poetry") if isinstance(tool, dict) else None
    if isinstance(poetry, dict):
        add_keys(poetry.get("dependencies"))
        add_keys(poetry.get("dev-dependencies"))
        groups = poetry.get("group")
        if isinstance(groups, dict):
            for group in groups.values():
                if isinstance(group, dict):
                    add_keys(group.get("dependencies"))
    return names


def _is_requirements_file(path: Path) -> bool:
    name = path.name.lower()
    if fnmatch.fnmatch(name, "requirements*.txt"):
        return True
    return path.suffix.lower() == ".txt" and path.parent.name == "requirements"


def detect_frameworks(root: str | os.PathLike) -> list[Framework]:
    """Return frameworks found in manifests under `root`, sorted by ecosystem then name.

    Each framework is reported once, with the first manifest (walk order,
    shallowest first) that mentioned it as `source`.
    """
    root = Path(root)
    found: dict[str, Framework] = {}

    def add(name: str, ecosystem: str, path: Path) -> None:
        found.setdefault(
            name, Framework(name, ecosystem, path.relative_to(root).as_posix())
        )

    for path in iter_files(root):
        lower = path.name.lower()

        if lower == "package.json":
            text = read_text(path)
            if text is None:
                continue
            for dep in package_json_deps(text):
                if dep in JS_FRAMEWORKS:
                    add(JS_FRAMEWORKS[dep], "javascript", path)

        elif lower == "pyproject.toml" or _is_requirements_file(path):
            text = read_text(path)
            if text is None:
                continue
            names = (
                _pyproject_names(text)
                if lower == "pyproject.toml"
                else _requirements_names(text)
            )
            for name in names & PY_FRAMEWORKS.keys():
                add(PY_FRAMEWORKS[name], "python", path)

        elif lower == "pom.xml":
            text = read_text(path)
            if text is None:
                continue
            artifacts = _ARTIFACT_ID.findall(_XML_COMMENT.sub("", text))
            if any(a.startswith("spring-boot") for a in artifacts):
                add("Spring Boot", "java", path)

        elif lower in ("build.gradle", "build.gradle.kts"):
            text = read_text(path)
            if text is not None and _GRADLE_SPRING_BOOT.search(text):
                add("Spring Boot", "java", path)

    return sorted(found.values(), key=lambda f: (f.ecosystem, f.name))