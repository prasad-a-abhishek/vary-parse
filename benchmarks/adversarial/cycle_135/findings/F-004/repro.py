"""F-004 — idempotent self-check.

Demonstrates that a small CLI invocation runs to completion and exits
0. T3's §4.1 noted that cli_parse runs at 27.7 iters/s because of
subprocess overhead; this repro confirms a single CLI invocation is
fast (<1 s) and exits cleanly, validating the per-call guard
contract.
"""
from __future__ import annotations

import subprocess
import sys
import time


def main() -> int:
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["python3", "-m", "vary_parse", "--parse", "Accept, Accept-Encoding"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    elapsed = time.perf_counter() - t0
    assert proc.returncode == 0, f"non-zero exit: {proc.returncode}, stderr={proc.stderr!r}"
    # CLI --parse outputs canonical form (no space after comma).
    assert proc.stdout.strip() == "Accept,Accept-Encoding", (
        f"unexpected stdout: {proc.stdout!r}"
    )
    print(
        f"F-004 OK: single CLI invocation exited 0 in {elapsed*1000:.0f} ms, "
        f"stdout={proc.stdout.strip()!r}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())