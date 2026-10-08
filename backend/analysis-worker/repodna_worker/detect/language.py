"""Language detection: count files and non-blank LOC per language by extension."""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = frozenset(
    {".git", "node_modules", "venv", ".venv", "dist", "build", "vendor", "__pycache__"}
)

EXTENSION_LANGUAGES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".dart": "Dart",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
}


@dataclass(frozen=True)
class LanguageStat:
    name: str
    files: int
    loc: int
    share: float  # fraction of total LOC, 0.0-1.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "files": self.files,
            "loc": self.loc,
            "share": self.share,
        }


def _count_loc(path: Path) -> int:
    """Non-blank lines in a file."""
    with path.open("rb") as f:
        return sum(1 for line in f if line.strip())


def detect_languages(root: str | os.PathLike) -> list[LanguageStat]:
    """Return languages used under `root`, sorted by share of code (desc).

    Only extensions in EXTENSION_LANGUAGES are counted. Ignored directories
    are pruned, and symlinks are never followed or counted.
    """
    files: dict[str, int] = defaultdict(int)
    loc: dict[str, int] = defaultdict(int)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for filename in filenames:
            language = EXTENSION_LANGUAGES.get(Path(filename).suffix.lower())
            if language is None:
                continue
            path = Path(dirpath) / filename
            if path.is_symlink():
                continue
            try:
                lines = _count_loc(path)
            except OSError:
                continue
            files[language] += 1
            loc[language] += lines

    total = sum(loc.values())
    stats = [
        LanguageStat(
            name=name,
            files=files[name],
            loc=loc[name],
            share=round(loc[name] / total, 4) if total else 0.0,
        )
        for name in files
    ]
    stats.sort(key=lambda s: (-s.loc, s.name))
    return stats