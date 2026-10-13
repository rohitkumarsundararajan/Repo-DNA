"""The real analysis stages, wired together for the pipeline orchestrator.

Each module of the analysis (detect, parse, metrics, graph, architecture, scoring,
assembler) was written and tested on its own. This file is the one place that
calls them in order and converts their output into exactly the shapes the next
step, and finally contract/result.schema.json, expect:

  * graph edges use {"from", "to"} (the builder uses source/target)
  * architecture.pattern is lower case and evidence is a flat list of file paths
  * architecture.violations lives inside `architecture`
  * languages use file_count / percentage (0-100); frameworks use name / category
  * the scorer needs plain dicts (it silently scores 100 for objects), and its
    keys are renamed to architecture_dna / code_dna / quality_dna
  * one-file "cycles" (self imports) are dropped; the schema needs two or more files

The Stages object keeps a little per-job state (repo folder, detection output).
That is safe because the worker runs one job at a time.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterator

from ..architecture.patterns import detect_pattern
from ..architecture.violations import detect_violations
from ..assembler.assemble import assemble
from ..detect.frameworks import detect_frameworks
from ..detect.language import detect_languages
from ..graph.builder import DependencyGraph, GraphBuilder
from ..graph.cycles import find_cycles
from ..metrics.aggregate import build_metrics
from ..metrics.cyclomatic import compute_file_complexity
from ..parsing.models import ParsedFile
from ..parsing.runner import parse_repository
from ..sandbox.acquire import acquire_source
from . import config
from .pipeline import Stages

log = logging.getLogger("repodna.stages")

# Must match contract/result.schema.json. Bump together with the schema.
SCHEMA_VERSION = "1.0.0"
MAX_EVIDENCE_FILES = 200


class UnsupportedRepositoryError(ValueError):
    """The repository has no source files the analysis understands."""


# --------------------------------------------------------------------------- #
# Pure shaping helpers (no I/O, easy to test)
# --------------------------------------------------------------------------- #
def graph_to_contract(graph: DependencyGraph) -> dict[str, Any]:
    """DependencyGraph -> {"nodes": [...], "edges": [{"from", "to"}]} (deterministic)."""
    nodes = [graph.nodes[path].to_dict() for path in sorted(graph.nodes)]
    edges = [
        {"from": source, "to": target}
        for source in sorted(graph.adjacency)
        for target in sorted(graph.adjacency[source])
    ]
    return {"nodes": nodes, "edges": edges}


def clean_cycles(cycles: list[list[str]]) -> list[list[str]]:
    """Drop one-file cycles (self imports); the contract requires at least two files."""
    return [list(cycle) for cycle in cycles if len(cycle) >= 2]


def flatten_evidence(evidence: Any) -> list[str]:
    """Turn the pattern detector's evidence structure into a flat list of file paths."""
    found: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, str):
            found.add(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in ("from", "to") and isinstance(item, str):
                    found.add(item)
                else:
                    visit(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)

    if isinstance(evidence, dict) and set(evidence) == {"reason"}:
        return []  # "Unknown" pattern: only an explanation, no files
    visit(evidence)
    return sorted(found)[:MAX_EVIDENCE_FILES]


def build_architecture(graph: DependencyGraph) -> dict[str, Any]:
    pattern = detect_pattern(graph)
    violations = detect_violations(graph)["violations"]
    return {
        "pattern": str(pattern["pattern"]).lower(),
        "evidence": flatten_evidence(pattern.get("evidence")),
        "violations": violations,
    }


def languages_to_contract(stats) -> list[dict[str, Any]]:
    return [
        {
            "name": stat.name,
            "file_count": stat.files,
            "loc": stat.loc,
            "percentage": round(stat.share * 100, 2),
        }
        for stat in stats
    ]


def frameworks_to_contract(frameworks) -> list[dict[str, Any]]:
    return [{"name": item.name, "category": item.ecosystem} for item in frameworks]


def scores_to_contract(raw: dict[str, float]) -> dict[str, float]:
    return {
        "architecture_dna": raw["architecture"],
        "code_dna": raw["code"],
        "quality_dna": raw["quality"],
    }


# --------------------------------------------------------------------------- #
# Stages
# --------------------------------------------------------------------------- #
class AnalysisStages:
    """Real implementations of every pipeline stage."""

    def __init__(
        self,
        acquire: Callable[[dict], ContextManager[Path]] = acquire_source,
        parse_workers: int | None = None,
    ) -> None:
        self._acquire_source = acquire
        self._parse_workers = parse_workers if parse_workers is not None else (config.PARSE_WORKERS or None)
        self._repo: Path | None = None
        self._detection: dict[str, Any] | None = None

    # -- stage 1: get the source ------------------------------------------------
    @contextmanager
    def acquire(self, job: dict) -> Iterator[Path]:
        self._repo = None
        self._detection = None
        try:
            with self._acquire_source(job) as repo:
                self._repo = Path(repo)
                yield self._repo
        finally:
            self._repo = None
            self._detection = None

    # -- stage 2: detect languages and frameworks -------------------------------
    def detect(self, repo: Path) -> dict[str, Any]:
        languages = detect_languages(repo)
        frameworks = detect_frameworks(repo)
        self._detection = {
            "languages": languages_to_contract(languages),
            "frameworks": frameworks_to_contract(frameworks),
            "total_files": sum(item.files for item in languages),
            "total_loc": sum(item.loc for item in languages),
        }
        return self._detection

    # -- stage 3: parse ---------------------------------------------------------
    def parse(self, repo: Path, detection: Any) -> list[ParsedFile]:
        parsed = parse_repository(repo, max_workers=self._parse_workers)
        if not parsed:
            raise UnsupportedRepositoryError(
                "No Python, JavaScript or TypeScript source files were found in this repository"
            )
        return parsed

    # -- stage 4: metrics -------------------------------------------------------
    def compute_metrics(self, parsed: list[ParsedFile]) -> dict[str, Any]:
        repo = self._require_repo()
        files, hotspots = build_metrics(parsed, repo)

        # Per-function numbers for the Code DNA score (it needs functions, not files).
        scoring_files = []
        for item in parsed:
            functions = compute_file_complexity(repo / item.path, root=repo)
            scoring_files.append(
                {
                    "path": item.path,
                    "functions": [
                        {
                            "name": fn.function,
                            "complexity": fn.complexity,
                            "lines": fn.end_line - fn.start_line + 1,
                        }
                        for fn in functions
                    ],
                }
            )
        return {"files": files, "hotspots": hotspots, "scoring_files": scoring_files}

    # -- stages 5-8: graph, cycles, architecture, scores ---------------------------
    def build_graph(self, parsed: list[ParsedFile]) -> DependencyGraph:
        return GraphBuilder(self._require_repo()).build(parsed)

    def find_cycles(self, graph: DependencyGraph) -> list[list[str]]:
        return clean_cycles(find_cycles(graph))

    def detect_architecture(self, graph: DependencyGraph, parsed: list[ParsedFile]) -> dict[str, Any]:
        return build_architecture(graph)

    def compute_scores(
        self, graph: DependencyGraph, cycles: list[list[str]], architecture: dict[str, Any], metrics: dict[str, Any]
    ) -> dict[str, float]:
        from ..scoring.dna import calculate_dna_scores

        raw = calculate_dna_scores(
            files=metrics["scoring_files"],
            graph=graph_to_contract(graph),
            architecture=architecture,
            cycles=cycles,
        )
        return scores_to_contract(raw)

    # -- stage 9: assemble ----------------------------------------------------------
    def assemble(
        self,
        job: dict,
        graph: DependencyGraph,
        cycles: list[list[str]],
        architecture: dict[str, Any],
        metrics: dict[str, Any],
        scores: dict[str, float],
    ) -> dict[str, Any]:
        detection = self._detection or {"languages": [], "frameworks": [], "total_files": 0, "total_loc": 0}
        return assemble(
            schema_version=SCHEMA_VERSION,
            job_id=job["job_id"],
            repo_meta={
                "repo_url": job.get("repo_url"),
                "source_type": job["source_type"],
                "total_files": detection["total_files"],
                "total_loc": detection["total_loc"],
                "analyzed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            languages=detection["languages"],
            frameworks=detection["frameworks"],
            files=metrics["files"],
            hotspots=metrics["hotspots"],
            graph=graph_to_contract(graph),
            cycles=cycles,
            architecture=architecture,
            scores=scores,
        )

    def _require_repo(self) -> Path:
        if self._repo is None:
            raise RuntimeError("no repository is open; acquire() must run first")
        return self._repo

    def as_stages(self) -> Stages:
        return Stages(
            acquire=self.acquire,
            detect=self.detect,
            parse=self.parse,
            compute_metrics=self.compute_metrics,
            build_graph=self.build_graph,
            find_cycles=self.find_cycles,
            detect_architecture=self.detect_architecture,
            compute_scores=self.compute_scores,
            assemble=self.assemble,
        )


def build_stages() -> Stages:
    return AnalysisStages().as_stages()
