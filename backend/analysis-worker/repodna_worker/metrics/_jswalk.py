"""Shared tree-sitter walker for JS/TS/TSX cognitive complexity and nesting.

Parses a file once and walks each function's body once, computing both
cognitive complexity and max nesting depth together in that single pass --
cognitive.py and nesting.py both call analyze_js_file() and project out the
one metric they need, instead of parsing and walking the file twice.

Rule (deliberately simple, per spec): every branch/loop construct adds
1 + <current nesting depth> to complexity, and nesting depth increases by
1 for everything inside it. This is not the full SonarSource algorithm
used for Python (see cognitive.py) -- confirm the exact rules with the
team if the two need to be numerically comparable.
"""

from __future__ import annotations

import os
import re
from bisect import bisect_left
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

JS_EXTENSIONS = frozenset(
    {".js", ".jsx", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".tsx"}
)

_GRAMMAR_KEYS = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
}

# Mirrors parsing/parser.py's own function-node detection; kept independent
# here since this module does a plain tree walk rather than a query.
_FUNCTION_DECLS = {"function_declaration", "generator_function_declaration", "method_definition"}
_FUNCTION_EXPRS = {"arrow_function", "function_expression", "generator_function"}
_FUNCTION_NODES = _FUNCTION_DECLS | _FUNCTION_EXPRS

_BRANCH_TYPES = {
    "if_statement",
    "for_statement",
    "for_in_statement",  # covers both for-in and for-of
    "while_statement",
    "do_statement",
    "switch_statement",
    "catch_clause",
    "ternary_expression",
}


@lru_cache(maxsize=None)
def _language(key: str) -> Language:
    if key == "javascript":
        return Language(tree_sitter_javascript.language())
    if key == "typescript":
        return Language(tree_sitter_typescript.language_typescript())
    if key == "tsx":
        return Language(tree_sitter_typescript.language_tsx())
    raise ValueError(f"unsupported grammar: {key}")


@dataclass(frozen=True)
class JsFunctionMetrics:
    name: str
    start_line: int
    end_line: int
    complexity: int
    max_nesting: int


def _text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def _field(node: Node, *names: str) -> Node | None:
    for name in names:
        child = node.child_by_field_name(name)
        if child is not None:
            return child
    return None


def _func_name(node: Node) -> str | None:
    """Best-effort name for a function/arrow/method node.

    Does not qualify methods with their class (tree-sitter gives no cheap
    way to do that here), matching the same limitation already noted for
    lizard in cyclomatic.py.
    """
    name = _field(node, "name")
    if name is not None:
        return _text(name) or None
    parent = node.parent
    if parent is None:
        return None
    if parent.type == "variable_declarator":
        return _text(parent.child_by_field_name("name")) or None
    if parent.type in ("field_definition", "public_field_definition"):
        return _text(_field(parent, "property", "name")) or None
    return None


def _collect_functions(root: Node) -> list[Node]:
    """Function/arrow/method nodes, not descending into nested ones."""
    found: list[Node] = []

    def walk(node: Node) -> None:
        for child in node.children:
            if child.type in _FUNCTION_NODES:
                found.append(child)
                continue  # its own body is scanned separately, see below
            walk(child)

    walk(root)
    return found


def _analyze_body(body: Node | None) -> tuple[int, int]:
    """(complexity, max_nesting) for one function's body."""
    complexity = 0
    max_nesting = 0

    def walk(node: Node, depth: int) -> None:
        nonlocal complexity, max_nesting
        for child in node.children:
            if child.type in _FUNCTION_NODES:
                continue  # nested closures are scored on their own
            if child.type in _BRANCH_TYPES:
                here = depth + 1
                complexity += here
                max_nesting = max(max_nesting, here)
                walk(child, here)
            else:
                walk(child, depth)

    if body is not None:
        walk(body, 0)
    return complexity, max_nesting


class _LineIndex:
    """Byte offset -> 1-based line number (see parsing/parser.py for why
    Node.start_point/.end_point are avoided)."""

    def __init__(self, source: bytes) -> None:
        self._newlines = [m.start() for m in re.finditer(b"\n", source)]

    def start(self, node: Node) -> int:
        return bisect_left(self._newlines, node.start_byte) + 1

    def end(self, node: Node) -> int:
        last = max(node.end_byte - 1, node.start_byte)
        return bisect_left(self._newlines, last) + 1


def analyze_js_file(path: str | os.PathLike) -> list[JsFunctionMetrics]:
    """Cognitive complexity and max nesting for every function in one file.

    Returns [] for an unsupported extension. Does not guard file size or
    symlinks -- callers (cognitive.py, nesting.py) do that before calling
    this, consistent with the rest of the metrics modules.
    """
    path = Path(path)
    key = _GRAMMAR_KEYS.get(path.suffix.lower())
    if key is None:
        return []

    source = path.read_bytes()
    tree = Parser(_language(key)).parse(source)
    lines = _LineIndex(source)

    results = []
    for func in _collect_functions(tree.root_node):
        name = _func_name(func)
        if not name:
            continue
        complexity, max_nesting = _analyze_body(_field(func, "body"))
        results.append(
            JsFunctionMetrics(
                name=name,
                start_line=lines.start(func),
                end_line=lines.end(func),
                complexity=complexity,
                max_nesting=max_nesting,
            )
        )
    return results