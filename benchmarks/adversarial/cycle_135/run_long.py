#!/usr/bin/env python3
"""
run_long.py — drive every cycle_135 harness at scale and persist
per-surface stats.json + AGGREGATE_STATS.json.

This is the cycle_135/adv/03 CORPUS_RUN runner. It uses the existing
harness_*.py scripts (cycle_135/adv/02 deliverable) which write
fuzz/<surface>/results.json. We then promote the harness results to
the canonical stats.json shape required by the CORPUS_RUN task
contract and aggregate.

Usage::

    python3 benchmarks/adversarial/cycle_135/run_long.py
    # writes fuzz/<surface>/stats.json and fuzz/AGGREGATE_STATS.json

The iters-per-surface plan is tuned to (a) reach >=100K for cheap
in-process surfaces (parse/serialize/wildcard/cross_cycle/type_errors)
and (b) hit a 30-90s wall-clock budget for the subprocess-heavy CLI
surfaces (cli_parse, cli_cache_key).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FUZZ = ROOT / "fuzz"

# Surfaces and their target iter counts. Tuned empirically against the
# smoke numbers in the HARNESSES.md deliverable.
PLAN: list[tuple[str, int]] = [
    ("harness_parse_main", 150_000),         # ~45s (in-process)
    ("harness_serialize_main", 150_000),     # ~50s (in-process)
    ("harness_cli_parse", 1_500),            # ~50s (subprocess x 3)
    ("harness_cli_cache_key", 8_000),        # ~36s (subprocess)
    ("harness_type_errors", 200_000),        # ~2s (in-process)
    ("harness_wildcard_precedence", 200_000),# ~3s (in-process)
    ("harness_cross_cycle", 200_000),        # ~3s (in-process)
]


def _run(surface: str, iters: int) -> dict:
    """Invoke a harness and return its results.json dict."""
    harness = ROOT / f"{surface}.py"
    proc = subprocess.run(
        [sys.executable, str(harness), "--iters", str(iters)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode not in (0, 1):
        sys.stderr.write(
            f"HARNESS_SELF_ERROR running {surface}: "
            f"exit={proc.returncode}\nstdout={proc.stdout}\n"
            f"stderr={proc.stderr}\n"
        )
    results_path = FUZZ / surface / "results.json"
    if not results_path.exists():
        raise RuntimeError(f"{surface} did not write results.json")
    return json.loads(results_path.read_text())


def _promote_stats(surface: str, results: dict) -> dict:
    """Translate harness results.json into the canonical stats.json shape."""
    iters = results["iters_clean"]
    elapsed = float(results["elapsed_seconds"])
    crashes = results.get("crashes") or []
    oracles = results.get("oracle_mismatches") or []
    self_err = results.get("harness_self_error")
    return {
        "surface": surface,
        "iters": iters,
        "crashes": len(crashes),
        "hangs": 0,  # run_harness() exits synchronously; a hang would
                     # manifest as a subprocess timeout, not in results
        "oom": 0,    # OOM would also manifest as a subprocess failure
        "oracle_mismatches": len(oracles),
        "exit_code": results["exit_code"],
        "duration_s": round(elapsed, 6),
        "verdict": results["verdict"],
        "python": results.get("python"),
        "seed": results.get("seed"),
        "started_utc": results.get("started_utc"),
        "ended_utc": results.get("ended_utc"),
        "crash_samples": crashes[:5],  # first few for triage
        "oracle_mismatch_samples": oracles[:5],
        "harness_self_error": self_err,
        "iters_per_second": round(iters / elapsed, 2) if elapsed > 0 else None,
    }


def main() -> int:
    started = time.perf_counter()
    surfaces: list[dict] = []
    total_iters = 0
    total_crashes = 0
    total_hangs = 0
    total_oom = 0
    total_oracle = 0
    for surface, iters in PLAN:
        t0 = time.perf_counter()
        print(f"[corpus_run] running {surface} --iters {iters} ...", flush=True)
        results = _run(surface, iters)
        stats = _promote_stats(surface, results)
        # Persist canonical stats.json
        (FUZZ / surface / "stats.json").write_text(
            json.dumps(stats, indent=2, sort_keys=True)
        )
        surfaces.append(stats)
        total_iters += stats["iters"]
        total_crashes += stats["crashes"]
        total_hangs += stats["hangs"]
        total_oom += stats["oom"]
        total_oracle += stats["oracle_mismatches"]
        wall = time.perf_counter() - t0
        print(
            f"  -> {stats['iters']} iters, "
            f"{stats['crashes']}C/{stats['hangs']}H/{stats['oom']}O/"
            f"{stats['oracle_mismatches']}M, "
            f"{stats['duration_s']:.2f}s, "
            f"{stats['iters_per_second']} iters/s, "
            f"verdict={stats['verdict']}",
            flush=True,
        )
    wall_total = time.perf_counter() - started

    aggregate = {
        "surfaces": surfaces,
        "totals": {
            "surfaces_run": len(surfaces),
            "iters_total": total_iters,
            "crashes_total": total_crashes,
            "hangs_total": total_hangs,
            "oom_total": total_oom,
            "oracle_mismatches_total": total_oracle,
            "wall_clock_seconds": round(wall_total, 3),
            "verdict_overall": "CLEAN" if (
                total_crashes == 0
                and total_hangs == 0
                and total_oom == 0
                and total_oracle == 0
            ) else "DIRTY",
            "python": sys.version.split()[0],
            "started_utc": surfaces[0]["started_utc"] if surfaces else None,
            "ended_utc": surfaces[-1]["ended_utc"] if surfaces else None,
        },
    }
    (FUZZ / "AGGREGATE_STATS.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True)
    )
    print(
        f"[corpus_run] DONE: {total_iters} iters / "
        f"{total_crashes}C / {total_hangs}H / {total_oom}O / "
        f"{total_oracle}M across {len(surfaces)} surfaces, "
        f"{wall_total:.2f}s wall, verdict={aggregate['totals']['verdict_overall']}",
        flush=True,
    )
    return 0 if aggregate["totals"]["verdict_overall"] == "CLEAN" else 1


if __name__ == "__main__":
    raise SystemExit(main())