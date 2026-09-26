"""Package manager and build tool detection.

Package managers come from lockfiles/manifests by filename; JS build tools
come from package.json dependency names. Files are only read, never executed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ._fs import iter_files, package_json_deps, read_text

PACKAGE_MANAGER = "package_manager"
BUILD_TOOL = "build_tool"

# Lowercased filename -> (tool, kind)
FILE_MARKERS = {
    "package-lock.json": ("npm", PACKAGE_MANAGER),
    "npm-shrinkwrap.json": ("npm", PACKAGE_MANAGER),
    "yarn.lock": ("yarn", PACKAGE_MANAGER),
    "pnpm-lock.yaml": ("pnpm", PACKAGE_MANAGER),
    "bun.lock": ("bun", PACKAGE_MANAGER),
    "bun.lockb": ("bun", PACKAGE_MANAGER),
    "poetry.lock": ("poetry", PACKAGE_MANAGER),
    "pipfile": ("pipenv", PACKAGE_MANAGER),
    "pipfile.lock": ("pipenv", PACKAGE_MANAGER),
    "uv.lock": ("uv", PACKAGE_MANAGER),
    "requirements.txt": ("pip", PACKAGE_MANAGER),
    "pom.xml": ("maven", PACKAGE_MANAGER),
    "build.gradle": ("gradle", PACKAGE_MANAGER),
    "build.gradle.kts": ("gradle", PACKAGE_MANAGER),
    "settings.gradle": ("gradle", PACKAGE_MANAGER),
    "settings.gradle.kts": ("gradle", PACKAGE_MANAGER),
    "cargo.lock": ("cargo", PACKAGE_MANAGER),
    "go.mod": ("go modules", PACKAGE_MANAGER),
    "gemfile.lock": ("bundler", PACKAGE_MANAGER),
    "composer.lock": ("composer", PACKAGE_MANAGER),
    "makefile": ("make", BUILD_TOOL),
    "cmakelists.txt": ("cmake", BUILD_TOOL),
}

JS_BUILD_TOOLS = {
    "vite": "vite",
    "webpack": "webpack",
    "rollup": "rollup",
    "esbuild": "esbuild",
    "parcel": "parcel",
    "turbo": "turbo",
}


@dataclass(frozen=True)
class BuildTool:
    name: str
    kind: str  # "package_manager" | "build_tool"
    source: str  # file path relative to the repo root (posix)

    def to_dict(self) -> dict:
        return {"name": self.name, "kind": self.kind, "source": self.source}


def detect_build_tools(root: str | os.PathLike) -> list[BuildTool]:
    """Return package managers and build tools under `root`, sorted by kind then name.

    Each tool is reported once, with the first file (shallowest first) that
    revealed it as `source`.
    """
    root = Path(root)
    found: dict[str, BuildTool] = {}

    def add(name: str, kind: str, path: Path) -> None:
        found.setdefault(
            name, BuildTool(name, kind, path.relative_to(root).as_posix())
        )

    for path in iter_files(root):
        lower = path.name.lower()

        marker = FILE_MARKERS.get(lower)
        if marker:
            add(marker[0], marker[1], path)

        if lower == "package.json":
            text = read_text(path)
            if text is None:
                continue
            for dep in package_json_deps(text):
                if dep in JS_BUILD_TOOLS:
                    add(JS_BUILD_TOOLS[dep], BUILD_TOOL, path)

    return sorted(found.values(), key=lambda t: (t.kind, t.name))