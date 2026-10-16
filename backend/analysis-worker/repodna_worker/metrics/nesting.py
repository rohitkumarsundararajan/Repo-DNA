"""Max nesting depth per function for Python and JS/TS.

Python walks the ast directly. JS/TS/TSX reuse the same tree-sitter pass
as cognitive.py (see _jswalk.py) rather than re-parsing the file: cognitive
complexity and max nesting are computed together in one walk, and this
module just projects out the nesting number.
"""

from __future__ import annotations

import ast
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ._jswalk import JS_EXTENSIONS, analyze_js_file
from ._paths import display_path
from ._pyast import iter_python_functions

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 1024 * 1024
PYTHON_EXTENSIONS = frozenset({".py"})
SUPPORTED_EXTENSIONS = PYTHON_EXTENSIONS | JS_EXTENSIONS

# Mirrors _jswalk.py's _BRANCH_TYPES as closely as the two languages allow:
# if/elif, for, while, except, and the ternary operator.
_PY_BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp)


@dataclass(frozen=True)
class NestingDepth:
    file: str
    function: str
    max_nesting: int
    start_line: int
    end_line: int

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "function": self.function,
            "max_nesting": self.max_nesting,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


def _python_max_nesting(node: ast.AST) -> int:
    max_depth = 0

    def walk(n: ast.AST, depth: int) -> None:
        nonlocal max_depth
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue  # nested closures are scored on their own
            if isinstance(child, _PY_BRANCH_NODES):
                here = depth + 1
                max_depth = max(max_depth, here)
                walk(child, here)
            else:
                walk(child, depth)

    walk(node, 0)
    return max_depth


def _python_nesting(path: Path, root: str | os.PathLike | None) -> list[NestingDepth]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    display = display_path(path, root)
    return [
        NestingDepth(
            file=display,
            function=fn.qualname,
            max_nesting=_python_max_nesting(fn.node),
            start_line=fn.node.lineno,
            end_line=fn.node.end_lineno,
        )
        for fn in iter_python_functions(tree)
    ]


def _js_nesting(path: Path, root: str | os.PathLike | None) -> list[NestingDepth]:
    display = display_path(path, root)
    return [
        NestingDepth(
            file=display,
            function=fm.name,
            max_nesting=fm.max_nesting,
            start_line=fm.start_line,
            end_line=fm.end_line,
        )
        for fm in analyze_js_file(path)
    ]


def compute_file_nesting(
    path: str | os.PathLike, root: str | os.PathLike | None = None
) -> list[NestingDepth]:
    """Max nesting depth per function for one file.

    Returns [] for unsupported extensions, symlinks, unreadable or
    oversized (>1 MB) files. Never raises: failures are logged and also
    yield [] for that file.
    """
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return []

    try:
        if path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
            return []
    except OSError:
        return []

    display = display_path(path, root)
    try:
        if path.suffix.lower() in PYTHON_EXTENSIONS:
            return _python_nesting(path, root)
        return _js_nesting(path, root)
    except Exception:
        logger.warning("failed to compute nesting for %s", display, exc_info=True)
        return []


def compute_repo_nesting(
    paths: Iterable[str | os.PathLike], root: str | os.PathLike | None = None
) -> list[NestingDepth]:
    """Max nesting depth across many files, sorted by file then line."""
    results: list[NestingDepth] = []
    for path in paths:
        results.extend(compute_file_nesting(path, root=root))
    results.sort(key=lambda n: (n.file, n.start_line))
    return results