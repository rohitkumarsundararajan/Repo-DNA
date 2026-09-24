"""Tree-sitter parser: source files -> ParsedFile.

Supports Python, JavaScript (incl. JSX) and TypeScript (incl. TSX). Other
languages come in later phases. Files are only read and parsed, never executed.
"""

from __future__ import annotations

import logging
import os
import re
from bisect import bisect_left
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser, Query, QueryCursor

from .models import CallInfo, ClassInfo, FunctionInfo, ImportInfo, ParsedFile

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 1024 * 1024
BINARY_SNIFF_BYTES = 8192
_MAX_DOTTED_CALLEE_BYTES = 200

# extension -> grammar key
EXTENSION_GRAMMARS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
}

_PY_QUERY = """
(import_statement) @import
(import_from_statement) @import_from
(function_definition) @function
(class_definition) @class
(call) @call
"""

_JS_COMMON_QUERY = """
(import_statement) @import
(export_statement source: (string)) @reexport
(function_declaration) @function
(generator_function_declaration) @function
(method_definition) @function
(variable_declarator
  name: (identifier)
  value: [(arrow_function) (function_expression)]) @varfunc
(class_declaration) @class
(call_expression) @call
(new_expression) @new
"""

_JS_QUERY = _JS_COMMON_QUERY + "(field_definition) @field\n"
_TS_QUERY = (
    _JS_COMMON_QUERY
    + "(public_field_definition) @field\n(abstract_class_declaration) @class\n"
)

_DOTTED = re.compile(r"^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$")


# --------------------------------------------------------------------------
# Model adapters: the only place that touches parsing/models.py constructors.
# --------------------------------------------------------------------------


def _make_import(module: str, names: list[str], level: int) -> ImportInfo:
    """`level` is the number of leading dots of a Python relative import (0 otherwise).

    JS/TS specifiers keep their raw text ("./utils", "../lib/x") as `module`
    with level 0; `is_relative` is True for anything starting with ".".
    """
    return ImportInfo(
        module=module,
        names=names,
        is_relative=level > 0 or module.startswith("."),
        level=level,
    )


def _make_function(name: str, start_line: int, end_line: int, loc: int) -> FunctionInfo:
    return FunctionInfo(name=name, start_line=start_line, end_line=end_line, loc=loc)


def _make_class(name: str, start_line: int, end_line: int, loc: int) -> ClassInfo:
    return ClassInfo(name=name, start_line=start_line, end_line=end_line, loc=loc)


def _make_call(name: str, start_line: int, caller: str | None) -> CallInfo:
    return CallInfo(name=name, start_line=start_line, caller=caller)


def _make_parsed_file(
    path: str,
    language: str,
    loc: int,
    imports: list[ImportInfo],
    functions: list[FunctionInfo],
    classes: list[ClassInfo],
    calls: list[CallInfo],
) -> ParsedFile:
    return ParsedFile(
        path=path,
        language=language,
        loc=loc,
        imports=imports,
        functions=functions,
        classes=classes,
        calls=calls,
    )


# --------------------------------------------------------------------------
# Grammars and queries
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Grammar:
    name: str  # ParsedFile.language
    language: Language
    query: Query


@lru_cache(maxsize=None)
def _grammar(key: str) -> _Grammar:
    if key == "python":
        lang, src, name = Language(tree_sitter_python.language()), _PY_QUERY, "python"
    elif key == "javascript":
        lang = Language(tree_sitter_javascript.language())
        src, name = _JS_QUERY, "javascript"
    elif key == "typescript":
        lang = Language(tree_sitter_typescript.language_typescript())
        src, name = _TS_QUERY, "typescript"
    elif key == "tsx":
        lang = Language(tree_sitter_typescript.language_tsx())
        src, name = _TS_QUERY, "typescript"
    else:
        raise ValueError(f"unsupported grammar: {key}")
    return _Grammar(name=name, language=lang, query=Query(lang, src))


# --------------------------------------------------------------------------
# Node helpers
# --------------------------------------------------------------------------


def _text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


class _LineIndex:
    """Byte offset -> 1-based line number.

    Deliberately avoids Node.start_point / Node.end_point: reading `.row` from
    them segfaulted for me on py-tree-sitter 0.26.0 (Python 3.12).
    """

    def __init__(self, source: bytes) -> None:
        self._newlines = [m.start() for m in re.finditer(b"\n", source)]
        # _nonblank[k] = number of non-blank lines among the first k lines
        self._nonblank = [0]
        for piece in source.split(b"\n"):
            self._nonblank.append(self._nonblank[-1] + (1 if piece.strip() else 0))

    @property
    def total_loc(self) -> int:
        """Non-blank lines in the file (same definition as detect/language.py)."""
        return self._nonblank[-1]

    def loc(self, start_line: int, end_line: int) -> int:
        """Non-blank lines in [start_line, end_line]."""
        last = len(self._nonblank) - 1
        return self._nonblank[min(end_line, last)] - self._nonblank[start_line - 1]

    def start(self, node: Node) -> int:
        return bisect_left(self._newlines, node.start_byte) + 1

    def end(self, node: Node) -> int:
        last = max(node.end_byte - 1, node.start_byte)
        return bisect_left(self._newlines, last) + 1


def _field(node: Node, *names: str) -> Node | None:
    for name in names:
        child = node.child_by_field_name(name)
        if child is not None:
            return child
    return None


def _string_value(node: Node | None) -> str | None:
    """Contents of a plain string literal; None for anything else."""
    text = _text(node)
    if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
        return text[1:-1]
    return None


def _callee_name(fn: Node | None) -> str | None:
    """`foo`, `a.b.c` as-is; `x().y` -> `y`; anything else -> None."""
    if fn is None:
        return None
    if fn.end_byte - fn.start_byte <= _MAX_DOTTED_CALLEE_BYTES:
        text = _text(fn)
        if _DOTTED.match(text):
            return text
    if fn.type in ("attribute", "member_expression"):
        last = _field(fn, "attribute", "property")
        return _text(last) or None
    return None


def _enclosing_function(node: Node, func_names: dict[int, str]) -> str | None:
    parent = node.parent
    while parent is not None:
        name = func_names.get(parent.id)
        if name is not None:
            return name
        parent = parent.parent
    return None


def _captures(grammar: _Grammar, root: Node) -> dict[str, list[Node]]:
    return QueryCursor(grammar.query).captures(root)


# --------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------


def _python_import_target(child: Node) -> str:
    target = child.child_by_field_name("name") if child.type == "aliased_import" else child
    return _text(target)


def _python_imports(node: Node) -> list[tuple[str, list[str], int]]:
    """(module, names, level) per imported module. Relative dots go to `level`."""
    if node.type == "import_statement":
        modules = [_python_import_target(c) for c in node.children_by_field_name("name")]
        return [(m, [], 0) for m in modules if m]

    raw = re.sub(r"\s+", "", _text(node.child_by_field_name("module_name")))
    if not raw:
        return []
    module = raw.lstrip(".")
    level = len(raw) - len(module)
    names = [_python_import_target(c) for c in node.children_by_field_name("name")]
    names = [n for n in names if n]
    if any(c.type == "wildcard_import" for c in node.children):
        names.append("*")
    return [(module, names, level)]


def _extract_python(caps: dict[str, list[Node]], lines: _LineIndex):
    imports = []
    for node in sorted(
        caps.get("import", []) + caps.get("import_from", []), key=lambda n: n.start_byte
    ):
        for module, names, level in _python_imports(node):
            imports.append((lines.start(node), module, names, level))

    func_names: dict[int, str] = {}
    functions = []
    for node in caps.get("function", []):
        name = _text(node.child_by_field_name("name"))
        if name:
            func_names[node.id] = name
            functions.append((lines.start(node), lines.end(node), name))

    classes = []
    for node in caps.get("class", []):
        name = _text(node.child_by_field_name("name"))
        if name:
            classes.append((lines.start(node), lines.end(node), name))

    calls = []
    for node in caps.get("call", []):
        callee = _callee_name(node.child_by_field_name("function"))
        if callee:
            calls.append((lines.start(node), callee, _enclosing_function(node, func_names)))

    return imports, functions, classes, calls


# --------------------------------------------------------------------------
# JavaScript / TypeScript
# --------------------------------------------------------------------------


def _js_import_names(node: Node) -> list[str]:
    names: list[str] = []
    clause = next((c for c in node.children if c.type == "import_clause"), None)
    if clause is None:
        return names
    for child in clause.named_children:
        if child.type == "identifier":
            names.append("default")
        elif child.type == "namespace_import":
            names.append("*")
        elif child.type == "named_imports":
            for spec in child.named_children:
                if spec.type == "import_specifier":
                    name = _text(spec.child_by_field_name("name"))
                    if name:
                        names.append(name)
    return names


def _js_reexport_names(node: Node) -> list[str]:
    clause = next((c for c in node.children if c.type == "export_clause"), None)
    if clause is None:
        return ["*"]
    names = [
        _text(spec.child_by_field_name("name"))
        for spec in clause.named_children
        if spec.type == "export_specifier"
    ]
    return [n for n in names if n]


def _js_import(node: Node) -> tuple[str, list[str]] | None:
    if node.type == "export_statement":
        module = _string_value(node.child_by_field_name("source"))
        return (module, _js_reexport_names(node)) if module else None

    source = node.child_by_field_name("source")
    if source is None:  # TS: import x = require("y")
        req = next((c for c in node.children if c.type == "import_require_clause"), None)
        if req is not None:
            source = next((c for c in req.children if c.type == "string"), None)
    module = _string_value(source)
    return (module, _js_import_names(node)) if module else None


def _first_string_arg(call: Node) -> str | None:
    args = call.child_by_field_name("arguments")
    if args is None or not args.named_children:
        return None
    return _string_value(args.named_children[0])


def _extract_js(caps: dict[str, list[Node]], lines: _LineIndex):
    imports = []
    for node in caps.get("import", []) + caps.get("reexport", []):
        parsed = _js_import(node)
        if parsed:
            imports.append((lines.start(node), parsed[0], parsed[1], 0))

    func_names: dict[int, str] = {}
    functions = []

    def add_function(fn: Node, name: str) -> None:
        if name:
            func_names[fn.id] = name
            functions.append((lines.start(fn), lines.end(fn), name))

    for node in caps.get("function", []):
        add_function(node, _text(node.child_by_field_name("name")))
    for node in caps.get("varfunc", []):
        fn = node.child_by_field_name("value")
        if fn is not None:
            add_function(fn, _text(node.child_by_field_name("name")))
    for node in caps.get("field", []):
        fn = node.child_by_field_name("value")
        if fn is not None and fn.type in ("arrow_function", "function_expression"):
            add_function(fn, _text(_field(node, "property", "name")))

    classes = []
    for node in caps.get("class", []):
        name = _text(node.child_by_field_name("name"))
        if name:
            classes.append((lines.start(node), lines.end(node), name))

    calls = []
    for node in caps.get("call", []):
        fn = node.child_by_field_name("function")
        if fn is not None and (
            fn.type == "import" or (fn.type == "identifier" and _text(fn) == "require")
        ):
            module = _first_string_arg(node)
            if module:
                imports.append((lines.start(node), module, [], 0))
            continue
        callee = _callee_name(fn)
        if callee:
            calls.append((lines.start(node), callee, _enclosing_function(node, func_names)))
    for node in caps.get("new", []):
        callee = _callee_name(node.child_by_field_name("constructor"))
        if callee:
            calls.append((lines.start(node), callee, _enclosing_function(node, func_names)))

    imports.sort(key=lambda i: i[0])
    calls.sort(key=lambda c: c[0])
    return imports, functions, classes, calls


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def _read_source(path: Path) -> bytes | None:
    """File bytes, or None if unreadable, a symlink, too large, or binary."""
    try:
        if path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        with path.open("rb") as fh:
            data = fh.read(MAX_FILE_BYTES + 1)
    except OSError:
        return None
    if len(data) > MAX_FILE_BYTES or b"\x00" in data[:BINARY_SNIFF_BYTES]:
        return None
    if data.startswith(b"\xef\xbb\xbf"):  # UTF-8 BOM
        data = data[3:]
    return data


def _display_path(path: Path, root: str | os.PathLike | None) -> str:
    if root is not None:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def parse_file(
    path: str | os.PathLike, root: str | os.PathLike | None = None
) -> ParsedFile | None:
    """Parse one source file into a ParsedFile.

    `ParsedFile.path` is relative to `root` when given, else the path as passed.
    `loc` counts non-blank lines (for the file and for each function/class).
    Returns None when the file is skipped: unsupported extension, symlink,
    unreadable, binary, or over 1 MB. Syntax errors never raise: tree-sitter
    recovers and whatever could be extracted is returned (logged at INFO).
    """
    path = Path(path)
    key = EXTENSION_GRAMMARS.get(path.suffix.lower())
    if key is None:
        return None
    source = _read_source(path)
    if source is None:
        return None

    grammar = _grammar(key)
    display = _display_path(path, root)
    lines = _LineIndex(source)

    try:
        tree = Parser(grammar.language).parse(source)
        caps = _captures(grammar, tree.root_node)
        extract = _extract_python if key == "python" else _extract_js
        imports, functions, classes, calls = extract(caps, lines)
        if tree.root_node.has_error:
            logger.info("syntax errors in %s; extracted best-effort", display)
    except Exception:  # never let one bad file take down the analysis
        logger.warning("failed to parse %s", display, exc_info=True)
        return _make_parsed_file(display, grammar.name, lines.total_loc, [], [], [], [])

    return _make_parsed_file(
        path=display,
        language=grammar.name,
        loc=lines.total_loc,
        imports=[_make_import(m, n, lvl) for _, m, n, lvl in imports],
        functions=[
            _make_function(name, start, end, lines.loc(start, end))
            for start, end, name in sorted(functions)
        ],
        classes=[
            _make_class(name, start, end, lines.loc(start, end))
            for start, end, name in sorted(classes)
        ],
        calls=[_make_call(callee, ln, caller) for ln, callee, caller in calls],
    )