#!/usr/bin/env python3
"""
harness_parse_main.py — fuzz the parse_vary() API surface.

V3 contract (cycle_135/adv/02, surface 1):
    stdin -> parse_vary(s) -> serialize_vary(parsed). Assert no uncaught
    exception (parse_vary is total — raises TypeError only on non-str input,
    which this harness never feeds). Every parsed result must round-trip
    through serialize_vary without throwing.

Inputs exercised: random bytes decoded as utf-8 (errors='replace'), plus
known-bad seeds.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make parent dir (where _harness_common.py lives) importable when run via
# `python3 harness_parse_main.py` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    adversarial_pool,
    random_str,
    run_harness,
)


def _drive(i: int, rng) -> None:
    from vary_parse import parse_vary, serialize_vary

    if i % 5 == 0:
        s = adversarial_pool(rng)
    else:
        s = random_str(rng)
    parsed = parse_vary(s)
    # Round-trip: serialize must never raise.
    ser = serialize_vary(parsed)
    # Sanity: serialized form must not contain raw CR/LF (RFC 9110 §5.5
    # prohibits header values that split over lines).
    if "\r" in ser or "\n" in ser:
        raise AssertionError(
            f"serialize_vary re-emitted CR/LF for input {s!r} -> {ser!r}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_parse_main",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
