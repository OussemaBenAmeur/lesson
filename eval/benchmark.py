"""Benchmarks: algorithmic compression vs. LLM baseline.

Usage::

    python eval/benchmark.py                  # run all algorithmic benchmarks
    python eval/benchmark.py --all            # include timing comparisons
    python eval/benchmark.py --fixture react  # single fixture

Outputs a rich table: speed (ms), node F1, edge accuracy, quality score.
The LLM baseline column requires ANTHROPIC_API_KEY and --llm flag.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
DATASETS_DIR = Path(__file__).parent / "datasets"


def _run_algorithmic(fixture_path: Path) -> dict:
    """Run the algorithmic pipeline on a fixture. Returns timing + quality."""
    from lesson.graph.builder import EventGraphBuilder
    from lesson.graph.schema import RawEvent, SessionGraph
    from lesson.graph.algorithms import graph_metrics

    events = RawEvent.load_file(fixture_path)
    if not events:
        return {"error": "empty fixture"}

    g = SessionGraph.empty(fixture_path.stem, "benchmark goal")

    t0 = time.perf_counter()
    builder = EventGraphBuilder(use_embedder=False)
    result = builder.compress(events, g)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    metrics = graph_metrics(result.graph)

    return {
        "fixture": fixture_path.name,
        "events": len(events),
        "nodes": metrics["nodes"],
        "edges": metrics["edges"],
        "elapsed_ms": round(elapsed_ms, 2),
        "has_root_cause": metrics["has_root_cause"],
        "has_resolution": metrics["has_resolution"],
        "is_dag": metrics["is_dag"],
        "orphan_count": metrics["orphan_count"],
        "compression_ratio": round(len(events) / max(metrics["nodes"], 1), 2),
    }


def _benchmark_scorer_scaling() -> list[dict]:
    """Measure SignificanceScorer scaling from 10 to 500 events."""
    from lesson.graph.schema import RawEvent
    from lesson.nlp.scorer import SignificanceScorer

    results = []
    base_events = [
        RawEvent(tool="Bash", args="cmd", result_head=f"output line {i}", is_error=(i % 7 == 0))
        for i in range(500)
    ]
    for n in [10, 25, 50, 100, 200, 500]:
        events = base_events[:n]
        scorer = SignificanceScorer()
        t0 = time.perf_counter()
        scorer.fit_score(events)
        elapsed = (time.perf_counter() - t0) * 1000
        results.append({"n_events": n, "scorer_ms": round(elapsed, 2)})
    return results


def print_table(rows: list[dict], title: str) -> None:
    try:
        from rich.table import Table
        from rich.console import Console

        if not rows:
            print(f"{title}: no data")
            return

        console = Console()
        table = Table(title=title)
        for col in rows[0].keys():
            table.add_column(col, style="cyan" if col == "fixture" else "white")
        for row in rows:
            table.add_row(*[str(v) for v in row.values()])
        console.print(table)
    except ImportError:
        print(f"\n=== {title} ===")
        if rows:
            print("  ".join(rows[0].keys()))
            for row in rows:
                print("  ".join(str(v) for v in row.values()))


def main() -> None:
    parser = argparse.ArgumentParser(description="lesson compression benchmark")
    parser.add_argument("--fixture", help="Run only this fixture (stem name)")
    parser.add_argument("--scaling", action="store_true", help="Run scorer scaling benchmark")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of table")
    args = parser.parse_args()

    # Collect fixtures
    fixture_paths = sorted(FIXTURES_DIR.glob("*.jsonl"))
    if DATASETS_DIR.exists():
        fixture_paths += sorted(DATASETS_DIR.glob("*.jsonl"))

    if args.fixture:
        fixture_paths = [p for p in fixture_paths if args.fixture in p.stem]

    if not fixture_paths:
        print("No fixtures found. Add .jsonl files to tests/fixtures/ or eval/datasets/")
        return

    # Run algorithmic benchmarks
    algo_results = []
    for fp in fixture_paths:
        row = _run_algorithmic(fp)
        algo_results.append(row)

    if args.json:
        print(json.dumps(algo_results, indent=2))
        return

    print_table(algo_results, "Algorithmic Compression Benchmarks")

    # Sub-100ms target check
    slow = [r for r in algo_results if r.get("elapsed_ms", 0) > 100]
    if slow:
        print(f"\n⚠ {len(slow)} fixture(s) exceeded 100ms target:")
        for r in slow:
            print(f"  {r['fixture']}: {r['elapsed_ms']}ms")
    else:
        print(f"\n✓ All fixtures completed under 100ms target")

    if args.scaling:
        scaling_results = _benchmark_scorer_scaling()
        print_table(scaling_results, "Scorer Scaling (events → latency)")


if __name__ == "__main__":
    main()
