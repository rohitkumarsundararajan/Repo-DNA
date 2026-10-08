"""Function and class LOC for Python and JS/TS.

Reuses parsing.parser.parse_file() (the same tree-sitter AST pass used for
imports/functions/classes/calls) instead of parsing files again: every
FunctionInfo/ClassInfo it produces already carries a `loc` field, so this
module just relabels that output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..parsing.models import ParsedFile
from ..parsing.parser import parse_file


@dataclass(frozen=True)
class FunctionSize:
    file: str
    function: str
    start_line: int
    end_line: int
    loc: int

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "function": self.function,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "loc": self.loc,
        }


@dataclass(frozen=True)
class ClassSize:
    file: str
    class_name: str
    start_line: int
    end_line: int
    loc: int

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "class_name": self.class_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "loc": self.loc,
        }


def _from_parsed(parsed: ParsedFile) -> tuple[list[FunctionSize], list[ClassSize]]:
    functions = [
        FunctionSize(
            file=parsed.path,
            function=f.name,
            start_line=f.start_line,
            end_line=f.end_line,
            loc=f.loc,
        )
        for f in parsed.functions
    ]
    classes = [
        ClassSize(
            file=parsed.path,
            class_name=c.name,
            start_line=c.start_line,
            end_line=c.end_line,
            loc=c.loc,
        )
        for c in parsed.classes
    ]
    return functions, classes


def compute_file_size(
    path: str | os.PathLike, root: str | os.PathLike | None = None
) -> tuple[list[FunctionSize], list[ClassSize]]:
    """Function and class LOC for one file, read off the tree-sitter parser.

    Returns ([], []) for anything parse_file() itself skips: unsupported
    extension, symlink, unreadable, binary, or over 1 MB.
    """
    parsed = parse_file(path, root=root)
    if parsed is None:
        return [], []
    return _from_parsed(parsed)


def compute_repo_size(
    paths: Iterable[str | os.PathLike], root: str | os.PathLike | None = None
) -> tuple[list[FunctionSize], list[ClassSize]]:
    """Function and class LOC across many files (each re-parsed once), sorted by file then line."""
    functions: list[FunctionSize] = []
    classes: list[ClassSize] = []
    for path in paths:
        fs, cs = compute_file_size(path, root=root)
        functions.extend(fs)
        classes.extend(cs)
    functions.sort(key=lambda f: (f.file, f.start_line))
    classes.sort(key=lambda c: (c.file, c.start_line))
    return functions, classes


def compute_size_from_parsed_files(
    parsed_files: Iterable[ParsedFile],
) -> tuple[list[FunctionSize], list[ClassSize]]:
    """Same output, but from ParsedFile objects you already have.

    Prefer this in the pipeline (task 13): parsing/runner.py (task 8)
    already parses every file once, so this avoids parsing a second time.
    """
    functions: list[FunctionSize] = []
    classes: list[ClassSize] = []
    for parsed in parsed_files:
        fs, cs = _from_parsed(parsed)
        functions.extend(fs)
        classes.extend(cs)
    functions.sort(key=lambda f: (f.file, f.start_line))
    classes.sort(key=lambda c: (c.file, c.start_line))
    return functions, classes