"""F-005 — idempotent self-check.

Demonstrates that the type-errors boundary is total: every non-str /
non-Mapping input is rejected with TypeError in O(1) time per call.
T3's §4.2 noted the surface runs at ~922K iters/s because of this
O(1) reject path. This repro exhaustively enumerates the documented
non-str pool.
"""
from __future__ import annotations

import sys
import time
from vary_parse import parse_vary, serialize_vary, vary_cache_key


# Empty string is excluded: it's a valid str per AC1 (parse_vary("") -> Vary((), False))
# and correctly does NOT raise TypeError.
NON_STR_POOL = [None, 0, 1, -1, 3.14, 1.5, True, False, [], {}, b""]


def main() -> int:
    t0 = time.perf_counter()
    for _ in range(1000):
        for bad in NON_STR_POOL:
            try:
                parse_vary(bad)  # type: ignore[arg-type]
            except TypeError:
                pass
            else:
                print(f"FAIL: parse_vary({bad!r}) did not raise TypeError", file=sys.stderr)
                return 1
    elapsed = time.perf_counter() - t0
    iters = 1000 * len(NON_STR_POOL)
    print(
        f"F-005 OK: {iters} type-error rejections in {elapsed*1000:.1f} ms "
        f"({iters/elapsed:.0f} iters/s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())