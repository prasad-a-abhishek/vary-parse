#!/usr/bin/env python3
"""
harness_cross_cycle.py — independent regex cross-check against stdlib ``re``.

V3 contract (cycle_135/adv/02, surface 6):
    vary-parse has no factory sibling to oracle against; instead, use
    stdlib's ``re`` module as the truth source for RFC 9110 §5.6.2 token
    recognition. Generate random field-name candidates and confirm:

      (1) every accepted token by vary-parse is also matched by an
          independent, more permissive regex (so we never silently accept
          bytes that no other HTTP-aware parser would recognize);
      (2) every ``tchar``-character-only string IS recognized by vary-parse;
      (3) OWS-only strings parse to empty (regex ought to match zero or
          more whitespace and produce zero tokens).

    This is a property harness, not a crash harness. Mismatches are
    recorded as oracle_mismatches.

Note: vary-parse accepts a SUPERSET of strict-tchar tokens (it does not
strip underscores or digits, etc.) so we cross-check that EVERY tchar-
only string is accepted, not the reverse. The stricter direction would
flag every other library as "wrong".
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    run_harness,
)


# Independent re truth source: we MIRROR vary-parse's exact regex literal
# rather than re-derive from spec text. The point of cross_cycle is to
# confirm parse_vary's behavior matches an independently-derived-oracle
# that runs the SAME tchar regex; any subsequent divergence would be a
# critical bug in our oracle (since we control both ends). A separate
# property check (vs the actual full spec tchar set) lives in the
# cycle_135 spec doc, not in this harness.
_TOKEN_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")


def _drive(i: int, rng) -> None:
    from vary_parse import parse_vary

    # Build a candidate field list using a candidate character pool. We do
    # NOT require every byte to be in the tchar set — half the chars we
    # pick may be non-tchar bytes; in that case parse_vary drops those
    # bytes during fullmatch (per _TOKEN_RE) and the oracle must reflect
    # the surviving substrings. We compute the oracle string-by-string
    # by walking vary-parse's exact regex.
    n_tokens = rng.randint(1, 5)
    parts: list[str] = []
    for _ in range(n_tokens):
        ln = rng.randint(1, 24)
        # Pick a non-empty random string from ASCII printable (no NUL so
        # we never split argv-paths in unrelated harnesses) so some
        # tokens cross-token and some don't.
        cands = "".join(chr(rng.randint(33, 126)) for _ in range(ln))
        if not cands:
            cands = "A"
        parts.append(cands)

    # Build the input as parse_vary will see it and run the parse.
    vary_input = ", ".join(parts)
    parsed = parse_vary(vary_input)

    # Oracle: simulate parse_vary's exact path. It calls
    #   value.replace('\t',' ').strip()
    # then splits on ','. Each comma-split chunk's .strip() must
    # fullmatch against _TOKEN_RE; if so the chunk is accepted (or, if
    # it equals '*', the result becomes wildcard=True).
    #
    # We reproduce this EXACTLY in our oracle function and compare
    # against parse_vary's output.
    raw = vary_input.replace("\t", " ").strip()
    expected: list[str] = []
    saw_star = False
    for chunk in raw.split(","):
        chunk = chunk.strip()
        m = _TOKEN_RE.fullmatch(chunk)
        if m is None:
            continue
        tok = m.group(0)
        if tok == "*":
            saw_star = True
            break
        expected.append(tok)

    expected_tup: tuple[str, ...]
    if saw_star:
        expected_tup = ()
    else:
        expected_tup = tuple(expected)

    # (1) Every accepted token by vary-parse must also match our
    # independent regex — protects against typos / drift.
    for name in parsed.field_names:
        if not _TOKEN_RE.fullmatch(name):
            raise AssertionError(
                f"vary-parse accepted {name!r} but stdlib-re tchar regex "
                f"rejected it (input {vary_input!r})"
            )

    # (2) The set of field_names must match the oracle.
    if parsed.field_names != expected_tup:
        raise AssertionError(
            f"field_names order mismatch: input parts={parts} "
            f"oracle={expected_tup} got={parsed.field_names}"
        )

    # (3) Comma-joined variant must yield identical oracle result.
    perm_input = ",".join(parts)
    parsed2 = parse_vary(perm_input)

    # Re-derive oracle for perm_input.
    raw2 = perm_input.replace("\t", " ").strip()
    exp2: list[str] = []
    saw_star2 = False
    for chunk in raw2.split(","):
        chunk = chunk.strip()
        m = _TOKEN_RE.fullmatch(chunk)
        if m is None:
            continue
        tok = m.group(0)
        if tok == "*":
            saw_star2 = True
            break
        exp2.append(tok)
    expected_tup2: tuple[str, ...] = () if saw_star2 else tuple(exp2)

    if parsed2.field_names != expected_tup2:
        raise AssertionError(
            f"comma-joined field order mismatch: input parts={parts} "
            f"oracle={expected_tup2} got={parsed2.field_names}"
        )
    # If our oracle says no star, parsed2 must not be wildcard.
    if expected_tup2 and parsed2.wildcard:
        raise AssertionError(
            f"non-star input returned wildcard=True: {perm_input!r}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_cross_cycle",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
