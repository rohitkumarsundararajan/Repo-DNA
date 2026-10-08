from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportInfo:
    module: str
    names: list[str] = field(default_factory=list)
    is_relative: bool = False
    level: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "names": list(self.names),
            "is_relative": self.is_relative,
            "level": self.level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportInfo:
        return cls(
            module=data["module"],
            names=list(data["names"]),
            is_relative=data["is_relative"],
            level=data["level"],
        )


@dataclass
class FunctionInfo:
    name: str
    start_line: int
    end_line: int
    loc: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "loc": self.loc,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FunctionInfo:
        return cls(
            name=data["name"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            loc=data["loc"],
        )


@dataclass
class ClassInfo:
    name: str
    start_line: int
    end_line: int
    loc: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "loc": self.loc,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassInfo:
        return cls(
            name=data["name"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            loc=data["loc"],
        )


@dataclass
class CallInfo:
    name: str
    start_line: int
    caller: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_line": self.start_line,
            "caller": self.caller,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CallInfo:
        return cls(
            name=data["name"],
            start_line=data["start_line"],
            caller=data["caller"],
        )


@dataclass
class ParsedFile:
    path: str
    language: str
    loc: int
    imports: list[ImportInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    calls: list[CallInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "loc": self.loc,
            "imports": [item.to_dict() for item in self.imports],
            "functions": [item.to_dict() for item in self.functions],
            "classes": [item.to_dict() for item in self.classes],
            "calls": [item.to_dict() for item in self.calls],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedFile:
        return cls(
            path=data["path"],
            language=data["language"],
            loc=data["loc"],
            imports=[ImportInfo.from_dict(item) for item in data["imports"]],
            functions=[FunctionInfo.from_dict(item) for item in data["functions"]],
            classes=[ClassInfo.from_dict(item) for item in data["classes"]],
            calls=[CallInfo.from_dict(item) for item in data["calls"]],
        )
