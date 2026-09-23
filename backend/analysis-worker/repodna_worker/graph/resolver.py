from __future__ import annotations

from pathlib import Path

from repodna_worker.parsing.models import ImportInfo, ParsedFile


class ImportResolver:
    """Resolve imports to files inside a repository."""

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()

    def resolve_import(
        self,
        parsed_file: ParsedFile,
        import_info: ImportInfo,
    ) -> Path | None:
        if parsed_file.language.lower() == "python":
            return self._resolve_python_import(parsed_file, import_info)

        if parsed_file.language.lower() in {
            "javascript",
            "typescript",
            "js",
            "ts",
        }:
            return self._resolve_js_ts_import(parsed_file, import_info)

        return None

    def _resolve_python_import(
        self,
        parsed_file: ParsedFile,
        import_info: ImportInfo,
    ) -> Path | None:
        """Resolve a Python import."""

        if import_info.is_relative:
            current_file = self.repo_root / parsed_file.path
            current_package = current_file.parent

            # level=1 means current package
            # level=2 means parent package
            # level=3 means grandparent package, etc.
            base = current_package

            for _ in range(import_info.level - 1):
                base = base.parent

            if import_info.module:
                module_path = Path(*import_info.module.split("."))
                base = base / module_path

            candidates = [
                base.with_suffix(".py"),
                base / "__init__.py",
            ]

            for candidate in candidates:
                if candidate.is_file():
                    return candidate.resolve()

            return None

        # Absolute import
        module_path = Path(*import_info.module.split("."))

        candidates = [
            self.repo_root / f"{module_path}.py",
            self.repo_root / module_path / "__init__.py",
        ]

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        return None

    def _resolve_js_ts_import(
        self,
        parsed_file: ParsedFile,
        import_info: ImportInfo,
    ) -> Path | None:
        """Resolve a JavaScript/TypeScript relative import."""

        # External packages such as "react" are not resolved.
        if not import_info.module.startswith("."):
            return None

        current_file = self.repo_root / parsed_file.path
        base = current_file.parent / import_info.module

        extensions = [".js", ".ts", ".tsx"]

        # Example:
        # ./UserService
        # -> UserService.js
        # -> UserService.ts
        # -> UserService.tsx
        for extension in extensions:
            candidate = Path(f"{base}{extension}")

            if candidate.is_file():
                return candidate.resolve()

        # Also support directory imports:
        # ./UserService
        # -> UserService/index.js
        # -> UserService/index.ts
        # -> UserService/index.tsx
        for extension in extensions:
            candidate = base / f"index{extension}"

            if candidate.is_file():
                return candidate.resolve()

        return None