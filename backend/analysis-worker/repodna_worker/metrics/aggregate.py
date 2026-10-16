"""Build contract-shaped file metrics and complexity hotspots."""

from __future__ import annotations

import ast
import json
import logging
import os
from pathlib import Path
from typing import Iterable

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from cognitive_complexity.api import get_cognitive_complexity
from tree_sitter import Language, Parser

from ..parsing.models import ParsedFile
from .cyclomatic import (
    JS_EXTENSIONS,
    PYTHON_EXTENSIONS,
    FunctionComplexity,
    compute_file_complexity,
)

logger = logging.getLogger(__name__)

TOP_N_HOTSPOTS = 10
_PYTHON_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Match,
)
_JS_NESTING_NODES = frozenset(
    {
        "if_statement",
        "for_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "switch_statement",
        "catch_clause",
    }
)
_JS_FUNCTION_NODES = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "method_definition",
        "arrow_function",
        "function_expression",
    }
)


def _python_metrics(source: str) -> tuple[int, int]:
    tree = ast.parse(source)
    cognitive = sum(
        get_cognitive_complexity(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )

    max_nesting = 0

    def visit(node: ast.AST, depth: int) -> None:
        nonlocal max_nesting
        if isinstance(node, _PYTHON_NESTING_NODES):
            depth += 1
            max_nesting = max(max_nesting, depth)
        for child in ast.iter_child_nodes(node):
            visit(child, depth)

    visit(tree, 0)
    return cognitive, max_nesting


def _javascript_language(extension: str) -> Language:
    if extension == ".tsx":
        return Language(tree_sitter_typescript.language_tsx())
    if extension in {".ts", ".mts", ".cts"}:
        return Language(tree_sitter_typescript.language_typescript())
    return Language(tree_sitter_javascript.language())


def _javascript_metrics(source: bytes, extension: str) -> tuple[int, int]:
    tree = Parser(_javascript_language(extension)).parse(source)
    max_nesting = 0
    cognitive = 0

    def functions(node):
        if node.type in _JS_FUNCTION_NODES:
            yield node
        for child in node.children:
            yield from functions(child)

    def function_cognitive_complexity(function_node) -> int:
        def visit(node, depth: int) -> int:
            if node is not function_node and node.type in _JS_FUNCTION_NODES:
                return 0

            is_nesting = node.type in _JS_NESTING_NODES
            score = 1 + depth if is_nesting else 0
            if node.type == "else_clause":
                score += 1
            elif node.type == "logical_expression":
                score += 1

            child_depth = depth + 1 if is_nesting else depth
            return score + sum(visit(child, child_depth) for child in node.children)

        return sum(visit(child, 0) for child in function_node.children)

    def visit(node, depth: int) -> None:
        nonlocal max_nesting
        if node.type in _JS_NESTING_NODES:
            depth += 1
            max_nesting = max(max_nesting, depth)
        for child in node.children:
            visit(child, depth)

    visit(tree.root_node, 0)
    cognitive = sum(function_cognitive_complexity(node) for node in functions(tree.root_node))
    return cognitive, max_nesting


def _source_metrics(path: Path) -> tuple[int, int]:
    try:
        source = path.read_bytes()
        extension = path.suffix.lower()
        if extension in PYTHON_EXTENSIONS:
            return _python_metrics(source.decode("utf-8", errors="replace"))
        if extension in JS_EXTENSIONS:
            return _javascript_metrics(source, extension)
    except (OSError, SyntaxError, ValueError):
        logger.warning("failed to compute cognitive/nesting metrics for %s", path)
    return 0, 0


def _hotspots(
    functions: list[FunctionComplexity], top_n: int
) -> list[dict[str, str | int]]:
    ranked = sorted(
        functions,
        key=lambda item: (-item.complexity, item.file, item.start_line, item.function),
    )
    return [
        {"path": item.file, "metric": "cyclomatic", "value": item.complexity}
        for item in ranked[:top_n]
    ]


def build_metrics(
    parsed_files: Iterable[ParsedFile],
    root: str | os.PathLike,
    top_n: int = TOP_N_HOTSPOTS,
) -> tuple[list[dict[str, str | int]], list[dict[str, str | int]]]:
    """Return contract-shaped per-file metrics and top function hotspots."""
    if top_n < 0:
        raise ValueError("top_n must be non-negative")

    root_path = Path(root)
    parsed = sorted(parsed_files, key=lambda item: item.path)
    complexity_by_file: dict[str, list[FunctionComplexity]] = {}
    all_functions: list[FunctionComplexity] = []

    for item in parsed:
        path = Path(item.path)
        source_path = path if path.is_absolute() else root_path / path
        functions = compute_file_complexity(source_path, root=root_path)
        complexity_by_file[item.path] = functions
        all_functions.extend(functions)

    files: list[dict[str, str | int]] = []
    for item in parsed:
        source_path = Path(item.path)
        if not source_path.is_absolute():
            source_path = root_path / source_path
        functions = complexity_by_file[item.path]
        cognitive, max_nesting = _source_metrics(source_path)
        files.append(
            {
                "path": item.path,
                "loc": item.loc,
                "cyclomatic": sum(function.complexity for function in functions),
                "cognitive": cognitive,
                "max_nesting": max_nesting,
            }
        )

    return files, _hotspots(all_functions, top_n)