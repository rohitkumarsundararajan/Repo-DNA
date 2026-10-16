"""Per-function cyclomatic complexity for Python and JS/TS.

Python goes through radon (radon.complexity.cc_visit); JavaScript and
TypeScript (including JSX/TSX) go through lizard. Both outputs are
normalised to the same FunctionComplexity shape. Files are only read and
analyzed, never executed.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import lizard
from radon.complexity import cc_visit
from radon.visitors import Function as RadonFunction

logger = logging.getLogger(__name__)

# Spec threshold: functions at or above this are flagged as too complex.
COMPLEXITY_THRESHOLD = 15

MAX_FILE_BYTES = 1024 * 1024

PYTHON_EXTENSIONS = frozenset({".py"})
JS_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".tsx"})
SUPPORTED_EXTENSIONS = PYTHON_EXTENSIONS | JS_EXTENSIONS


@dataclass(frozen=True)
class FunctionComplexity:
    file: str
    function: str
    complexity: int
    start_line: int
    end_line: int
    is_flagged: bool

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "function": self.function,
            "complexity": self.complexity,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "is_flagged": self.is_flagged,
        }


def _flagged(complexity: int) -> bool:
    return complexity >= COMPLEXITY_THRESHOLD


def _display_path(path: Path, root: str | os.PathLike | None) -> str:
    if root is not None:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _python_complexity(source: str, display: str) -> list[FunctionComplexity]:
    results = []
    for block in cc_visit(source):
        # cc_visit also yields Class blocks (a method-count aggregate) -- skip
        # those, we only want individual functions and methods.
        if not isinstance(block, RadonFunction):
            continue
        results.append(
            FunctionComplexity(
                file=display,
                function=block.fullname,  # "method" or "ClassName.method"
                complexity=block.complexity,
                start_line=block.lineno,
                end_line=block.endline,
                is_flagged=_flagged(block.complexity),
            )
        )
    return results


def _js_complexity(path: Path, display: str) -> list[FunctionComplexity]:
    # lizard reads the file itself; it does not raise on missing/binary
    # files, just returns no functions, so no extra guarding needed here.
    analyzed = lizard.analyze_file(str(path))
    return [
        FunctionComplexity(
            file=display,
            # lizard does not qualify JS/TS method names with their class.
            function=fn.name,
            complexity=fn.cyclomatic_complexity,
            start_line=fn.start_line,
            end_line=fn.end_line,
            is_flagged=_flagged(fn.cyclomatic_complexity),
        )
        for fn in analyzed.function_list
    ]


def compute_file_complexity(
    path: str | os.PathLike, root: str | os.PathLike | None = None
) -> list[FunctionComplexity]:
    """Per-function cyclomatic complexity for one file.

    Dispatches on extension: Python via radon, JS/TS/TSX via lizard.
    `FunctionComplexity.file` is relative to `root` when given.

    Returns [] for unsupported extensions, symlinks, unreadable or
    oversized (>1 MB) files. Never raises: a syntax error or any other
    analysis failure is logged as a warning and also yields [] for that
    file, so one bad file can't take down a whole repo's metrics.
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return []

    display = _display_path(path, root)

    try:
        if path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
            return []
    except OSError:
        return []

    try:
        if ext in PYTHON_EXTENSIONS:
            source = path.read_text(encoding="utf-8", errors="replace")
            return _python_complexity(source, display)
        return _js_complexity(path, display)
    except Exception:  # SyntaxError, OSError, or anything a parser throws
        logger.warning("failed to compute complexity for %s", display, exc_info=True)
        return []


def compute_repo_complexity(
    paths: Iterable[str | os.PathLike], root: str | os.PathLike | None = None
) -> list[FunctionComplexity]:
    """Per-function cyclomatic complexity across many files.

    Flattens compute_file_complexity() over `paths`, sorted by file then
    start line for a deterministic order.
    """
    results: list[FunctionComplexity] = []
    for path in paths:
        results.extend(compute_file_complexity(path, root=root))
    results.sort(key=lambda fc: (fc.file, fc.start_line))
    return results