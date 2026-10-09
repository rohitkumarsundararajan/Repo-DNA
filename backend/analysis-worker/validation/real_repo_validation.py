from __future__ import annotations

import sys
import time
from pathlib import Path

# Make repodna_worker importable when this file is executed directly.
WORKER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKER_ROOT))

from repodna_worker.parsing.runner import parse_repository
from repodna_worker.graph.builder import GraphBuilder
from repodna_worker.graph.cycles import find_cycles
from repodna_worker.architecture.patterns import detect_pattern
from repodna_worker.architecture.violations import detect_violations
from repodna_worker.scoring.dna import calculate_dna_scores


def validate_repository(repo_path: str) -> None:
    root = Path(repo_path).resolve()
    timings: dict[str, float] = {}
    overall_started = time.perf_counter()

    if not root.exists():
        raise FileNotFoundError(f"Repository does not exist: {root}")

    print("=" * 80)
    print(f"REPOSITORY: {root}")
    print("=" * 80)

    # 1. Parse repository
    print("\n[1] Parsing repository...")

    started = time.perf_counter()
    parsed_files = parse_repository(
        root,
        max_workers=4,
    )
    timings["parse"] = time.perf_counter() - started

    print(f"Parsed files: {len(parsed_files)}")

    # 2. Build dependency graph
    print("\n[2] Building dependency graph...")

    started = time.perf_counter()
    builder = GraphBuilder(root)
    graph = builder.build(parsed_files)
    timings["graph"] = time.perf_counter() - started

    print(f"Graph nodes: {len(graph.nodes)}")
    print(
        f"Graph edges: "
        f"{sum(len(targets) for targets in graph.adjacency.values())}"
    )

    # 3. Detect cycles
    print("\n[3] Detecting cycles...")

    started = time.perf_counter()
    cycles = find_cycles(graph)
    timings["cycles"] = time.perf_counter() - started

    print(f"Cycles found: {len(cycles)}")

    for index, cycle in enumerate(cycles[:10], start=1):
        print(f"  Cycle {index}:")
        for node in cycle:
            print(f"    {node}")

    if len(cycles) > 10:
        print(f"  ... {len(cycles) - 10} more cycles")

    # 4. Detect architecture
    print("\n[4] Detecting architecture pattern...")

    started = time.perf_counter()
    architecture = detect_pattern(graph)
    timings["architecture"] = time.perf_counter() - started

    print(f"Pattern: {architecture['pattern']}")
    print(f"Evidence: {architecture['evidence']}")

    # 5. Detect violations
    print("\n[5] Detecting architectural violations...")

    started = time.perf_counter()
    violation_result = detect_violations(graph)
    violations = violation_result["violations"]
    timings["violations"] = time.perf_counter() - started

    print(f"Violations found: {len(violations)}")

    for index, violation in enumerate(violations[:10], start=1):
        print(
            f"  {index}. "
            f"{violation['from']} -> "
            f"{violation['to']} "
            f"[{violation['rule']}]"
        )

    if len(violations) > 10:
        print(f"  ... {len(violations) - 10} more violations")

    # 6. DNA scores
    print("\n[6] Calculating DNA scores...")

    started = time.perf_counter()
    scores = calculate_dna_scores(
        graph=graph,
        cycles=cycles,
        architecture=architecture,
        files=parsed_files,
    )
    timings["scoring"] = time.perf_counter() - started

    print(f"Scores: {scores}")

    # 7. Basic sanity checks
    print("\n[7] Sanity checks...")

    assert len(parsed_files) >= 0
    assert len(graph.nodes) == len(parsed_files)

    for score_name, score in scores.items():
        assert 0 <= score <= 100, (
            f"{score_name} score out of range: {score}"
        )

    print("PASS: basic sanity checks")
    timings["total"] = time.perf_counter() - overall_started
    print(
        "TIMINGS: "
        + " ".join(f"{name}={seconds:.3f}s" for name, seconds in timings.items())
        + f" parsed_files={len(parsed_files)}"
    )

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    repository_paths = sys.argv[1:]
    if len(repository_paths) not in (1, 3):
        print(
            "Usage: python real_repo_validation.py <repository-path> "
            "[<small-repository> <medium-repository>]"
        )
        raise SystemExit(1)

    for repository_path in repository_paths:
        validate_repository(repository_path)