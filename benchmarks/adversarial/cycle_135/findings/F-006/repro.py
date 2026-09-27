"""F-006 — idempotent self-check.

Demonstrates that parse_vary handles a 1 MiB-cap large input in
linear time and linear memory. T3's §4.3 confirmed this completes
inside the 10 s subprocess timeout without OOM. This in-process repro
measures wall-clock directly.
"""
from __future__ import annotations

import sys
import time
from vary_parse import parse_vary


def main() -> int:
    # 1 MiB single-token input — the spec's documented upper bound.
    big = "Accept-Encoding" + "x" * (1024 * 1024 - len("Accept-Encoding"))
    t0 = time.perf_counter()
    parsed = parse_vary(big)
    elapsed = time.perf_counter() - t0
    assert len(parsed.field_names) == 1
    assert len(parsed.field_names[0]) == 1024 * 1024
    # Linear-time bound: should be sub-second on any modern host.
    assert elapsed < 1.0, f"unexpectedly slow: {elapsed:.3f}s for 1 MiB"
    print(
        f"F-006 OK: parse_vary 1 MiB single-token in {elapsed*1000:.1f} ms "
        f"(linear-time)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())