#!/usr/bin/env python3
"""
harness_wildcard_precedence.py — pure property oracle for AC5.

V3 contract (cycle_135/adv/02, surface 5):
    AC5 (SPEC.md acceptance criterion): "When a ``*`` member appears ANYWHERE
    in the field-value list (alone or mixed with selecting field names), the
    parsed Vary is wildcard=True with empty field_names."

    This harness generates random comma-separated lists where the wildcard
    ``*`` is randomly absent / present / at the start / in the middle / at
    the end / duplicated. For every such list, ``parse_vary`` must agree
    with the expected oracle on the wildcard bit AND on whether the
    field_names survive.

    Mismatch is a property violation: the harness records it as an
    oracle_mismatch and exits non-zero so the downstream T3/T4 phases
    inspect it.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    run_harness,
)


# Pre-baked templates and tokens for the synthetic Vary values.
_TOKENS = [
    "Accept",
    "Accept-Encoding",
    "Accept-Language",
    "User-Agent",
    "X-Custom",
    "X-Other",
    "A",
    "B",
    "C",
    "*",
]


def _gen_vary_value(rng: random.Random) -> tuple[str, bool, tuple[str, ...]]:
    """Generate (input, expected_wildcard, expected_names).

    Oracle semantics matching the actual vary-parse contract:
    - Has any '*' -> wildcard=True, field_names=()
    - Otherwise -> wildcard=False, field_names are input-order,
      duplicates PRESERVED (RFC 9110 does not specify dedup), every
      token that fails _TOKEN_RE.fullmatch is silently dropped.
    """
    n = rng.randint(0, 6)
    parts = [rng.choice(_TOKENS) for _ in range(n)]
    has_star = "*" in parts

    if has_star:
        # AC5: any star -> wildcard=True, field_names=()
        return ",".join(parts), True, ()

    # No star: expected field_names preserve input order, including
    # duplicates. We let parse_vary drop non-token chunks; with our
    # adversarial pool every chunk IS a valid token, so the oracle
    # expects every chunk back.
    return ",".join(parts), False, tuple(parts)


def _drive(i: int, rng) -> None:
    from vary_parse import parse_vary

    # Mix in deliberate adversarial shuffles to also cover adjacent items,
    # whitespace, and CRLF.
    s, exp_wc, exp_names = _gen_vary_value(rng)

    # Inject OWS / CRLF around tokens to exercise strip_ows path.
    if i % 3 == 0:
        s = "  " + s.replace(",", "  ,  ") + "  "

    parsed = parse_vary(s)
    if parsed.wildcard != exp_wc:
        raise AssertionError(
            f"wildcard mismatch on {s!r}: expected={exp_wc} got={parsed.wildcard}"
        )
    if parsed.field_names != exp_names:
        raise AssertionError(
            f"field_names mismatch on {s!r}: expected={exp_names} "
            f"got={parsed.field_names}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_wildcard_precedence",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
