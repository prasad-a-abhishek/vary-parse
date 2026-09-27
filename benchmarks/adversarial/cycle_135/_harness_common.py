"""
Shared harness utilities for the vary-parse adversary workstream (cycle_135).

Cycle_133-134 established the "subprocess-harness + JSON results envelope" pattern,
which avoids requiring Atheris/libFuzzer and produces artifacts readable by the
TRIAGE + FUZZING_REPORT phases.

Conventions
-----------
- Each harness script writes its results to ``fuzz/<surface>/results.json``
  beside ``benchmarks/adversarial/cycle_135/``.
- Exit codes: 0 = clean (no crash, no oracle mismatch); 1 = crash (uncaught
  exception or oracle mismatch); 2 = harness self-error (bad config).
- The seed-PRNG is fixed so a re-run is bit-identical (helpful for oracle diffs).
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


# Fixed seed for deterministic oracle diffs across re-runs.
DEFAULT_SEED = 0xC0FFEE_1350_0001

# Anchor to the benchmark root so subprocess invocations from CI land the
# results.json file next to the harness_*.py source — matches the V4 deliverable.
ADVERSARIAL_ROOT = Path(__file__).resolve().parent
FUZZ_ROOT = ADVERSARIAL_ROOT / "fuzz"


def adversarial_root() -> Path:
    return ADVERSARIAL_ROOT


def fuzz_root() -> Path:
    return FUZZ_ROOT


def ensure_fuzz_dir(surface: str) -> Path:
    out = FUZZ_ROOT / surface
    out.mkdir(parents=True, exist_ok=True)
    return out


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_results(surface: str, payload: dict[str, Any]) -> Path:
    out = ensure_fuzz_dir(surface) / "results.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return out


def run_harness(
    *,
    surface: str,
    iters: int,
    fn: Callable[[int, random.Random], None],
    seed: int = DEFAULT_SEED,
) -> int:
    """Drive ``fn(iters, rng)`` and write results.json. Returns exit code.

    ``fn`` should raise on any unexpected (uncaught) exception or oracle
    mismatch — ``run_harness`` will translate that into exit code 1 and write
    a crash record into the results.
    """
    started = utc_now_iso()
    t0 = time.perf_counter()
    rng = random.Random(seed)
    crashes: list[dict[str, Any]] = []
    oracle_mismatches: list[dict[str, Any]] = []
    clean_iters = 0
    try:
        for i in range(iters):
            try:
                fn(i, rng)
                clean_iters += 1
            except AssertionError as e:
                oracle_mismatches.append(
                    {"iter": i, "kind": "AssertionError", "msg": str(e)}
                )
                # Continue rather than abort — count every mismatch.
            except Exception as e:  # noqa: BLE001 — uncaught means harness crash
                crashes.append(
                    {
                        "iter": i,
                        "kind": type(e).__name__,
                        "msg": str(e)[:500],
                    }
                )
    except Exception as e:  # noqa: BLE001 — harness self-error
        # Bad: the harness itself blew up. Write a degraded result and exit 2.
        elapsed = time.perf_counter() - t0
        write_results(
            surface,
            {
                "surface": surface,
                "iters_requested": iters,
                "iters_clean": clean_iters,
                "crashes": crashes,
                "oracle_mismatches": oracle_mismatches,
                "harness_self_error": {
                    "kind": type(e).__name__,
                    "msg": str(e)[:500],
                },
                "seed": seed,
                "started_utc": started,
                "ended_utc": utc_now_iso(),
                "elapsed_seconds": round(elapsed, 6),
                "exit_code": 2,
                "verdict": "HARNESS_SELF_ERROR",
            },
        )
        print(f"HARNESS_SELF_ERROR ({type(e).__name__}): {e}", file=sys.stderr)
        return 2

    elapsed = time.perf_counter() - t0
    exit_code = 0 if (not crashes and not oracle_mismatches) else 1
    verdict = "CLEAN" if exit_code == 0 else "DIRTY"
    write_results(
        surface,
        {
            "surface": surface,
            "iters_requested": iters,
            "iters_clean": clean_iters,
            "crashes": crashes,
            "oracle_mismatches": oracle_mismatches,
            "harness_self_error": None,
            "seed": seed,
            "started_utc": started,
            "ended_utc": utc_now_iso(),
            "elapsed_seconds": round(elapsed, 6),
            "exit_code": exit_code,
            "verdict": verdict,
            "python": sys.version.split()[0],
            "argv": sys.argv[1:],
        },
    )
    return exit_code


def random_str(rng: random.Random, *, max_len: int = 4096) -> str:
    """Generate a random str using a byte stream decoded as utf-8 with errors='replace'.

    This mirrors what an HTTP server typically sees after recv + decode: any
    byte is possible, including NUL, CR, LF, and arbitrary multi-byte sequences
    that decode to replacement chars.
    """
    n = rng.randint(0, max_len)
    raw = bytes(rng.randint(0, 255) for _ in range(n))
    return raw.decode("utf-8", errors="replace")


def adversarial_pool(rng: random.Random) -> str:
    """Pick a known-bad seed string from a small corpus.

    Mixes "interesting" HTTP-header values: empty, OWS-only, CRLF, multibyte,
    NUL, lone-star, multi-star, lowercase tokens, mixed-case, bad punctuation.
    """
    seeds = [
        "",
        "*",
        " * ",
        "*, *",
        "Accept",
        "Accept-Encoding, Accept-Language",
        "  Accept-Encoding  ,\tUser-Agent  ",
        "X-Custom-Flag, Accept-Language, x-other",
        "Accept,,User-Agent",
        "A, B, C",
        "  \t  ",
        "\r\n\r\n",
        "\x00\x00\x00",
        "Accept\r\nInjected: bad",
        "中文-Accept",  # multibyte chars
        "Star-*",
        "*-Star",
        "*, Accept",
        "Accept, *, User-Agent",
        "Accept-Encoding; bogus",
        "Accept (Encoding)",
        '"quoted"',
        "Bad\x80Char",  # invalid utf-8 stand-in
    ]
    return rng.choice(seeds)


def request_header_dict(rng: random.Random) -> dict[str, str]:
    """Generate a plausible request-headers dict for vary_cache_key fuzzing."""
    pool = [
        ("Accept", "*/*"),
        ("Accept-Encoding", "gzip, deflate"),
        ("Accept-Language", "en-US,en;q=0.9"),
        ("User-Agent", "Mozilla/5.0"),
        ("Cookie", "session=abc"),
        ("Authorization", "Bearer x"),
        ("X-Forwarded-For", "1.2.3.4"),
        ("Range", "bytes=0-99"),
        ("If-None-Match", '"abc"'),
        ("Cache-Control", "no-cache"),
        ("Pragma", "no-cache"),
        ("Referer", "https://example.com/"),
        ("Host", "example.com"),
        ("", "weird-empty-key"),
        ("weird-empty-value", ""),
        ("X-MixedCase-Header", "v"),
    ]
    n = rng.randint(0, len(pool))
    picked = rng.sample(pool, n) if n else []
    return dict(picked)
