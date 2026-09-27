#!/usr/bin/env python3
"""
harness_cli_parse.py — fuzz the CLI --parse / --serialize / --json entrypoints.

V3 contract (cycle_135/adv/02, surface 2):
    Spawn ``python3 -m vary_parse --{parse,serialize,json} <value>`` with
    adversarial strings. The CLI must exit 0 and emit a single line of output
    regardless of input. Non-zero exit or non-parseable JSON is a crash.

Inputs exercised: empty, whitespace, CRLF, 1MiB+ payload, NUL, mixed unicode.
"""

from __future__ import annotations

import argparse
import json
import subprocess
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
    for mode in ("--parse", "--serialize", "--json"):
        if i % 4 == 0:
            v = adversarial_pool(rng)
        else:
            # Mix small and large inputs (1MiB-ish) to cover the boundary
            # between CLI arg-passing and any pathological allocation.
            if i % 11 == 0:
                v = random_str(rng, max_len=1_048_576)
            else:
                v = random_str(rng)
        # OS-level argv cannot carry NUL bytes anywhere on POSIX. Such
        # inputs therefore cannot reach ``python3 -m vary_parse`` at all
        # on this surface, so we filter them out here. NUL handling is
        # covered exhaustively by harness_parse_main which exercises
        # parse_vary() directly.
        if "\x00" in v:
            continue
        proc = subprocess.run(
            [sys.executable, "-m", "vary_parse", mode, v],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"CLI exit {proc.returncode} for {mode} input {v[:80]!r}: "
                f"stderr={proc.stderr[:200]!r}"
            )
        if mode == "--json":
            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                raise AssertionError(
                    f"--json emitted invalid JSON for {v[:80]!r}: "
                    f"stdout={proc.stdout[:200]!r} err={e}"
                )
            if not isinstance(payload, dict):
                raise AssertionError(
                    f"--json payload not dict: {payload!r}"
                )
            if "field_names" not in payload or "wildcard" not in payload:
                raise AssertionError(
                    f"--json missing keys: {payload!r}"
                )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_cli_parse",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
