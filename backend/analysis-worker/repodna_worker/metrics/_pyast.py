"""Shared Python `ast` helpers for the cognitive and nesting metrics.

Collects module- and class-level functions without ever descending into a
function's own body, so nested closures are never reported as separate
entries. This matches cyclomatic.py, where radon.complexity.cc_visit
skips closures by default -- keeping the same set of "functions" reported
across all of cyclomatic/cognitive/nesting for a given Python file.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class PyFunction:
    node: ast.FunctionDef | ast.AsyncFunctionDef
    qualname: str  # "method" or "ClassName.method"


class _FunctionCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: list[PyFunction] = []
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self._class_stack.pop()

    def _record(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualname = ".".join((*self._class_stack, node.name))
        self.found.append(PyFunction(node, qualname))
        # Deliberately not calling generic_visit: a nested def is part of
        # this function's own complexity, not a separate reported entry.

    visit_FunctionDef = _record
    visit_AsyncFunctionDef = _record


def iter_python_functions(tree: ast.AST) -> list[PyFunction]:
    """Module- and class-level functions/methods, top to bottom.

    Conditionally-defined functions (inside `if`/`try`/`with` at module or
    class level) are still found, since generic_visit keeps walking those
    compound statements; only descent into a function's *own* body is
    suppressed.
    """
    collector = _FunctionCollector()
    collector.visit(tree)
    return collector.found