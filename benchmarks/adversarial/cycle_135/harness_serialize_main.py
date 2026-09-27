#!/usr/bin/env python3
"""
harness_serialize_main.py — idempotence: parse -> serialize -> parse.

V3 contract (cycle_135/adv/02, surface 1b):
    For every input string s, parse_vary(s) -> serialize_vary(parsed) ->
    parse_vary(serialized) must produce an IDENTICAL Vary tuple (idempotence
    of the parser/serializer pair). Mismatch is a property violation, not a
    crash; the harness records it as an oracle_mismatch.

Inputs exercised: random bytes + known-bad seeds (cross-coverage with
harness_parse_main).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    adversarial_pool,
    random_str,
    run_harness,
)


def _drive(i: int, rng) -> None:
    from vary_parse import parse_vary, serialize_vary

    if i % 7 == 0:
        s = adversarial_pool(rng)
    else:
        s = random_str(rng)
    p1 = parse_vary(s)
    ser = serialize_vary(p1)
    p2 = parse_vary(ser)
    if p1 != p2:
        raise AssertionError(
            f"idempotence violated: parse({s!r})={p1!r} -> ser={ser!r} -> "
            f"parse={p2!r}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_serialize_main",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
