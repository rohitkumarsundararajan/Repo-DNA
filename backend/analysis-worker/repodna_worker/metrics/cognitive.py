"""Per-function cognitive complexity for Python and JS/TS.

Python uses the cognitive-complexity package (a SonarSource-style
algorithm, via ast). JS/TS/TSX use a small tree-sitter walker: +1 per
branch, plus 1 more for each level of nesting it's inside (see _jswalk.py).
The two are not expected to be numerically comparable -- confirm the exact
rules with the team if that matters.
"""

from __future__ import annotations

import ast
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from cognitive_complexity.api import get_cognitive_complexity

from ._jswalk import JS_EXTENSIONS, analyze_js_file
from ._paths import display_path
from ._pyast import iter_python_functions

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 1024 * 1024
PYTHON_EXTENSIONS = frozenset({".py"})
SUPPORTED_EXTENSIONS = PYTHON_EXTENSIONS | JS_EXTENSIONS


@dataclass(frozen=True)
class CognitiveComplexity:
    file: str
    function: str
    complexity: int
    start_line: int
    end_line: int

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "function": self.function,
            "complexity": self.complexity,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


def _python_cognitive(path: Path, root: str | os.PathLike | None) -> list[CognitiveComplexity]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    display = display_path(path, root)
    return [
        CognitiveComplexity(
            file=display,
            function=fn.qualname,
            complexity=get_cognitive_complexity(fn.node),
            start_line=fn.node.lineno,
            end_line=fn.node.end_lineno,
        )
        for fn in iter_python_functions(tree)
    ]


def _js_cognitive(path: Path, root: str | os.PathLike | None) -> list[CognitiveComplexity]:
    display = display_path(path, root)
    return [
        CognitiveComplexity(
            file=display,
            function=fm.name,
            complexity=fm.complexity,
            start_line=fm.start_line,
            end_line=fm.end_line,
        )
        for fm in analyze_js_file(path)
    ]


def compute_file_cognitive_complexity(
    path: str | os.PathLike, root: str | os.PathLike | None = None
) -> list[CognitiveComplexity]:
    """Per-function cognitive complexity for one file.

    Dispatches on extension: Python via the cognitive-complexity package,
    JS/TS/TSX via the shared tree-sitter walker in _jswalk.py.

    Returns [] for unsupported extensions, symlinks, unreadable or
    oversized (>1 MB) files. Never raises: a syntax error or any other
    analysis failure is logged as a warning and also yields [] for that
    file.
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
            return _python_cognitive(path, root)
        return _js_cognitive(path, root)
    except Exception:
        logger.warning("failed to compute cognitive complexity for %s", display, exc_info=True)
        return []


def compute_repo_cognitive_complexity(
    paths: Iterable[str | os.PathLike], root: str | os.PathLike | None = None
) -> list[CognitiveComplexity]:
    """Per-function cognitive complexity across many files, sorted by file then line."""
    results: list[CognitiveComplexity] = []
    for path in paths:
        results.extend(compute_file_cognitive_complexity(path, root=root))
    results.sort(key=lambda c: (c.file, c.start_line))
    return results