#!/usr/bin/env python3
"""
harness_cli_cache_key.py — fuzz ``vary-parse --cache-key VARY REQ``.

V3 contract (cycle_135/adv/02, surface 2b):
    Spawn the CLI with random vary+req combinations. Whatever the vary
    input, the output must be either valid JSON (``null`` for wildcard, or
    ``{"vary_x": "y", ...}``) or a clean exit-2 with a ``vary-parse: bad
    --cache-key request header`` error. Anything else (non-zero exit,
    non-parseable JSON, partial output) is a crash.

The "bad request header" path exercises the CLI's graceful-degradation
contract — Vary header fuzzing must not crash an HTTP frontend.
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
    request_header_dict,
    run_harness,
)


def _req_to_csv(d: dict[str, str]) -> str:
    return ",".join(f"{k}={v}" for k, v in d.items())


def _drive(i: int, rng) -> None:
    vary_value = (
        adversarial_pool(rng) if i % 5 == 0 else random_str(rng)
    )
    # OS-level argv cannot carry NUL bytes; skip those inputs here. NUL
    # coverage lives in harness_parse_main.
    if "\x00" in vary_value:
        return
    req = request_header_dict(rng)
    req_csv = _req_to_csv(req)
    if "\x00" in req_csv:
        req_csv = req_csv.replace("\x00", "")

    # Inject a malformed pair on a fraction of iterations to hit the
    # graceful-error path.
    if i % 17 == 0:
        # Strip the '=' so the CLI's pair parser trips the bad-request branch.
        req_csv = "NoEqualsSign"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vary_parse",
            "--cache-key",
            vary_value,
            req_csv,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if proc.returncode == 2:
        # Graceful bad-input path is acceptable per the contract.
        if "bad --cache-key request header" not in proc.stderr:
            raise AssertionError(
                f"exit 2 but stderr does not match bad-request contract: "
                f"{proc.stderr[:200]!r}"
            )
        return

    if proc.returncode != 0:
        raise AssertionError(
            f"unexpected exit {proc.returncode} for vary={vary_value[:60]!r} "
            f"req={req_csv[:60]!r}: stderr={proc.stderr[:200]!r}"
        )

    # Exit 0 -> JSON object or null.
    out = proc.stdout.strip()
    if not out:
        raise AssertionError(
            f"empty stdout for vary={vary_value[:60]!r} req={req_csv[:60]!r}"
        )
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"invalid JSON output for vary={vary_value[:60]!r}: "
            f"{out[:200]!r} err={e}"
        )
    if payload is not None and not isinstance(payload, dict):
        raise AssertionError(f"JSON payload not null/dict: {payload!r}")
    if isinstance(payload, dict):
        for k in payload:
            if not k.startswith("vary_"):
                raise AssertionError(
                    f"cache-key key missing vary_ prefix: {k!r}"
                )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_cli_cache_key",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
